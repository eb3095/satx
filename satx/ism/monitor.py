"""rtl_433 subprocess lifecycle and message buffer."""

from __future__ import annotations

import select
import subprocess
import threading
import time
from collections import deque
from typing import Deque, Optional

import numpy as np

from satx.config import ISM_SAMPLE_RATE, MAX_ISM_MESSAGES, RadioConfig
from satx.ism.decoder import IsmMessage, Rtl433Decoder
from satx.log_writer import LogWriter
from satx.radio.hackrf import HackRFReceiver, _failure_line
from satx.radio.process_util import stop_subprocess

RECONNECT_DELAY_SEC = 1.0


class IsmMonitor:
    def __init__(
        self,
        freq_mhz: float,
        *,
        radio: RadioConfig,
        log_writer: LogWriter | None = None,
    ) -> None:
        self.freq_mhz = freq_mhz
        self._radio = radio
        self._log = log_writer
        self._decoder = Rtl433Decoder(freq_mhz)
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._hackrf_proc: Optional[subprocess.Popen[bytes]] = None
        self._messages: Deque[IsmMessage] = deque(maxlen=MAX_ISM_MESSAGES)
        self._want_run = False
        self._pipe_alive = False
        self._error: Optional[str] = None
        self._fatal_error: Optional[str] = None
        self._use_pipe = radio.backend == "hackrf" and not Rtl433Decoder.soapy_available()
        self._supervisor: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def available(self) -> bool:
        return self._decoder.available

    @property
    def backend(self) -> str:
        return self._radio.backend

    @property
    def messages(self) -> Deque[IsmMessage]:
        return self._messages

    @property
    def error(self) -> Optional[str]:
        return self._fatal_error or self._error

    @property
    def running(self) -> bool:
        return self._want_run

    @property
    def pipe_alive(self) -> bool:
        return self._pipe_alive

    def _build_hackrf_command(self) -> list[str]:
        hackrf = HackRFReceiver.find_binary()
        if not hackrf:
            raise RuntimeError(
                "hackrf_transfer not found. Install with: brew install hackrf"
            )
        freq_hz = int(round(self.freq_mhz * 1_000_000))
        return [
            hackrf,
            "-r",
            "-",
            "-f",
            str(freq_hz),
            "-s",
            str(ISM_SAMPLE_RATE),
            "-l",
            str(self._radio.lna_gain),
            "-g",
            str(self._radio.vga_gain),
            "-a",
            "1" if self._radio.amp_enable else "0",
        ]

    def start(self) -> None:
        if self._want_run:
            return
        if not self._decoder.available:
            self._fatal_error = "rtl_433 not installed — run: make deps"
            return
        self._fatal_error = None
        self._error = None
        self._want_run = True
        self._stop_event.clear()
        self._supervisor = threading.Thread(target=self._supervisor_loop, daemon=True)
        self._supervisor.start()

    def stop(self, *, fast: bool = False) -> None:
        self._want_run = False
        self._stop_event.set()
        self._kill_pipeline(fast=fast)
        if self._supervisor and self._supervisor.is_alive():
            self._supervisor.join(timeout=0.3 if fast else 3)
        self._supervisor = None
        self._pipe_alive = False

    def _kill_pipeline(self, *, fast: bool = False) -> None:
        if self._hackrf_proc:
            stop_subprocess(self._hackrf_proc, fast=fast, prefer_sigint=not fast)
            self._hackrf_proc = None
        if self._proc:
            stop_subprocess(self._proc, fast=fast)
            self._proc = None

    def _supervisor_loop(self) -> None:
        while self._want_run and not self._stop_event.is_set():
            try:
                self._run_pipeline()
            except RuntimeError as exc:
                self._fatal_error = str(exc)
                self._want_run = False
                break
            if not self._want_run or self._stop_event.is_set():
                break
            self._error = "reconnecting…"
            self._stop_event.wait(RECONNECT_DELAY_SEC)
        self._pipe_alive = False
        self._error = None

    def _run_pipeline(self) -> None:
        if self._radio.backend == "rtlsdr":
            rtl_cmd = self._decoder.build_rtlsdr_command()
            hackrf_cmd = None
        elif self._use_pipe:
            HackRFReceiver.check_device()
            rtl_cmd = self._decoder.build_pipe_command()
            hackrf_cmd = self._build_hackrf_command()
        else:
            rtl_cmd = self._decoder.build_sdr_command()
            hackrf_cmd = None

        self._kill_pipeline()
        self._proc = subprocess.Popen(
            rtl_cmd,
            stdin=subprocess.PIPE if self._use_pipe else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        if self._use_pipe:
            assert hackrf_cmd is not None
            self._hackrf_proc = subprocess.Popen(
                hackrf_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            if self._hackrf_proc.poll() is not None:
                self._set_hackrf_error(
                    "hackrf_transfer failed to start — check USB connection"
                )
                self._kill_pipeline()
                return

        if self._proc.poll() is not None:
            self._set_rtl_error("rtl_433 failed to start")
            self._kill_pipeline()
            return

        self._pipe_alive = True
        self._error = None
        feed = (
            threading.Thread(target=self._feed_loop, daemon=True)
            if self._use_pipe
            else None
        )
        reader = threading.Thread(target=self._reader_loop, daemon=True)
        if feed is not None:
            feed.start()
        reader.start()
        if feed is not None:
            feed.join()
        reader.join()
        self._pipe_alive = False
        if self._want_run and not self._fatal_error:
            if self._hackrf_proc and self._hackrf_proc.poll() is not None:
                self._set_hackrf_error(
                    "hackrf_transfer exited — check USB connection"
                )
            elif self._proc and self._proc.poll() is not None:
                code = self._proc.returncode
                if code not in (0, None):
                    self._set_rtl_error(f"rtl_433 exited with code {code}")
            self._kill_pipeline()

    def _set_hackrf_error(self, fallback: str) -> None:
        message = fallback
        if self._hackrf_proc and self._hackrf_proc.stderr:
            text = self._hackrf_proc.stderr.read().decode("utf-8", errors="replace")
            parsed = _failure_line(text) if text.strip() else None
            if parsed and parsed != "HackRF unavailable":
                message = parsed
        self._error = message

    def _set_rtl_error(self, message: str) -> None:
        self._error = message

    def _feed_loop(self) -> None:
        assert self._hackrf_proc is not None
        assert self._proc is not None
        hackrf_out = self._hackrf_proc.stdout
        rtl_in = self._proc.stdin
        if hackrf_out is None or rtl_in is None:
            return
        try:
            while self._want_run and not self._stop_event.is_set():
                if self._hackrf_proc.poll() is not None:
                    break
                ready, _, _ = select.select([hackrf_out], [], [], 0.5)
                if not ready:
                    continue
                chunk = hackrf_out.read(65536)
                if not chunk:
                    break
                if len(chunk) % 2:
                    chunk = chunk[:-1]
                iq = np.frombuffer(chunk, dtype=np.int8)
                rtl_in.write((iq.astype(np.int16) * 256).tobytes())
                rtl_in.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                rtl_in.close()
            except OSError:
                pass

    def _reader_loop(self) -> None:
        assert self._proc is not None
        stdout = self._proc.stdout
        if stdout is None:
            return
        fd = stdout.fileno()
        buffer = b""
        while self._want_run and not self._stop_event.is_set():
            if self._proc.poll() is not None:
                break
            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                continue
            chunk = stdout.read(4096)
            if not chunk:
                if self._proc.poll() is not None:
                    break
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                msg = Rtl433Decoder.parse_line(text)
                if msg is None:
                    continue
                self._messages.appendleft(msg)
                if self._log is not None:
                    self._log.log_ism(msg.summary())

    def poll(self) -> None:
        return

    def ensure_running(self) -> None:
        if not self._want_run:
            self.start()
