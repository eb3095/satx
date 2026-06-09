"""HackRF One IQ capture via hackrf_transfer."""

from __future__ import annotations

import os
import select
import shutil
import subprocess
from typing import Optional

from satx.radio.process_util import stop_subprocess
from satx.config import (
    CHUNK_SAMPLES,
    HACKRF_BINARY_PATHS,
    SAMPLE_RATE,
    RadioConfig,
)

HACKRF_INFO_PATHS = (
    "hackrf_info",
    "/opt/homebrew/bin/hackrf_info",
    "/usr/local/bin/hackrf_info",
)


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
    return lines[0] if lines else "HackRF unavailable"


class HackRFReceiver:
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
        return _find_binary(HACKRF_BINARY_PATHS)

    @staticmethod
    def find_info_binary() -> Optional[str]:
        return _find_binary(HACKRF_INFO_PATHS)

    @staticmethod
    def check_device() -> None:
        if HackRFReceiver.find_binary() is None:
            raise RuntimeError(
                "hackrf_transfer not found. Install with: brew install hackrf"
            )
        info = HackRFReceiver.find_info_binary()
        if info is None:
            return
        try:
            result = subprocess.run(
                [info],
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"HackRF check failed: {exc}") from exc
        if result.returncode == 0:
            return
        text = result.stderr.decode("utf-8", errors="replace").strip()
        if not text:
            text = result.stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeError(_failure_line(text))

    def _build_command(self, hackrf: str) -> list[str]:
        return [
            hackrf,
            "-r",
            "-",
            "-f",
            str(self._freq_hz),
            "-s",
            str(self._sample_rate),
            "-l",
            str(self._config.lna_gain),
            "-g",
            str(self._config.vga_gain),
            "-a",
            "1" if self._config.amp_enable else "0",
        ]

    def _probe_start_failure(self, cmd: list[str]) -> str:
        probe = list(cmd)
        try:
            dash = probe.index("-")
            if dash + 1 < len(probe) and probe[dash + 1] == "-":
                probe[dash + 1] = os.devnull
        except ValueError:
            pass
        try:
            result = subprocess.run(
                probe,
                capture_output=True,
                timeout=2,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "hackrf_transfer timed out while opening HackRF"
        text = result.stderr.decode("utf-8", errors="replace").strip()
        if not text:
            text = result.stdout.decode("utf-8", errors="replace").strip()
        if text:
            return _failure_line(text)
        if result.returncode not in (0, None):
            return f"hackrf_transfer failed with exit code {result.returncode}"
        return "hackrf_transfer failed to start"

    def start(self) -> None:
        self.check_device()
        hackrf = self.find_binary()
        assert hackrf is not None
        cmd = self._build_command(hackrf)
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
                f"hackrf_transfer exited with code {code}. "
                "Check USB connection and close other HackRF apps."
            )
        return (
            "hackrf_transfer exited unexpectedly. "
            "Check USB connection and close other HackRF apps."
        )

    def stop(self, *, fast: bool = False) -> None:
        if self._proc:
            stop_subprocess(self._proc, fast=fast, prefer_sigint=not fast)
            self._proc = None
