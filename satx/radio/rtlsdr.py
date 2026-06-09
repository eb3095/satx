"""RTL-SDR IQ capture via rtl_sdr."""

from __future__ import annotations

import os
import select
import shutil
import subprocess
from typing import Optional

from satx.config import CHUNK_SAMPLES, RTL_SDR_BINARY_PATHS, SAMPLE_RATE, RadioConfig
from satx.radio.process_util import stop_subprocess

RTL_TEST_PATHS = ("rtl_test", "/opt/homebrew/bin/rtl_test", "/usr/local/bin/rtl_test")


def _find_binary(candidates: tuple[str, ...]) -> Optional[str]:
    for candidate in candidates:
        path = shutil.which(candidate) if "/" not in candidate else candidate
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _failure_line(text: str) -> str:
    for line in text.splitlines():
        lowered = line.lower()
        if "failed" in lowered or "error" in lowered or "denied" in lowered:
            return line.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else "RTL-SDR unavailable"


class RtlSdrReceiver:
    def __init__(
        self,
        config: RadioConfig,
        *,
        freq_hz: int,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self._config = config
        self._freq_hz = freq_hz
        self._sample_rate = sample_rate
        self._proc: Optional[subprocess.Popen[bytes]] = None

    @staticmethod
    def find_binary() -> Optional[str]:
        return _find_binary(RTL_SDR_BINARY_PATHS)

    @staticmethod
    def find_test_binary() -> Optional[str]:
        return _find_binary(RTL_TEST_PATHS)

    @staticmethod
    def check_device() -> None:
        if RtlSdrReceiver.find_binary() is None:
            raise RuntimeError("rtl_sdr not found. Install with: brew install rtl-sdr")
        rtl_test = RtlSdrReceiver.find_test_binary()
        if rtl_test is None:
            return
        try:
            result = subprocess.run(
                [rtl_test, "-t"],
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"RTL-SDR check failed: {exc}") from exc
        if result.returncode == 0:
            return
        text = result.stderr.decode("utf-8", errors="replace").strip()
        if not text:
            text = result.stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeError(_failure_line(text))

    def _build_command(self, rtl_sdr: str) -> list[str]:
        return [
            rtl_sdr,
            "-f",
            str(self._freq_hz),
            "-s",
            str(self._sample_rate),
            "-g",
            str(self._config.tuner_gain),
            "-p",
            str(self._config.ppm_error),
            "-",
        ]

    def _probe_start_failure(self, cmd: list[str]) -> str:
        probe = list(cmd)
        if probe and probe[-1] == "-":
            probe[-1] = os.devnull
        try:
            result = subprocess.run(
                probe,
                capture_output=True,
                timeout=2,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "rtl_sdr timed out while opening RTL-SDR"
        text = result.stderr.decode("utf-8", errors="replace").strip()
        if not text:
            text = result.stdout.decode("utf-8", errors="replace").strip()
        if text:
            return _failure_line(text)
        if result.returncode not in (0, None):
            return f"rtl_sdr failed with exit code {result.returncode}"
        return "rtl_sdr failed to start"

    def start(self) -> None:
        self.check_device()
        rtl_sdr = self.find_binary()
        assert rtl_sdr is not None
        cmd = self._build_command(rtl_sdr)
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        if self._proc.poll() is not None:
            message = self._probe_start_failure(cmd)
            self._proc = None
            raise RuntimeError(message)

    def read_chunk(self, timeout: float = 0.05) -> bytes:
        if not self._proc or not self._proc.stdout:
            return b""
        fd = self._proc.stdout.fileno()
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            return b""
        return os.read(fd, CHUNK_SAMPLES * 2)

    def set_frequency(self, freq_hz: int) -> None:
        if freq_hz == self._freq_hz:
            return
        running = self.running
        if running:
            self.stop()
        self._freq_hz = freq_hz
        if running:
            self.start()

    @property
    def freq_hz(self) -> int:
        return self._freq_hz

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def exited(self) -> bool:
        return self._proc is not None and self._proc.poll() is not None

    def exit_error(self) -> str | None:
        if not self.exited or self._proc is None:
            return None
        code = self._proc.returncode
        if code == 0:
            return None
        if code is not None:
            return (
                f"rtl_sdr exited with code {code}. "
                "Check USB connection and close other SDR apps."
            )
        return (
            "rtl_sdr exited unexpectedly. "
            "Check USB connection and close other SDR apps."
        )

    def stop(self, *, fast: bool = False) -> None:
        if self._proc:
            stop_subprocess(self._proc, fast=fast, prefer_sigint=not fast)
            self._proc = None
