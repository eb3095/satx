"""rtl_433 JSON decoder for ISM band sensors."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from satx.config import ISM_SAMPLE_RATE


@dataclass
class IsmMessage:
    timestamp: str
    model: str
    payload: dict[str, Any]
    level: Optional[float] = None
    frequency: Optional[str] = None

    def summary(self) -> str:
        parts = [self.model]
        for key in ("id", "channel", "temperature_F", "humidity", "pressure_hPa"):
            if key in self.payload:
                parts.append(f"{key}={self.payload[key]}")
        if self.level is not None:
            parts.append(f"level={self.level:.1f}")
        return " ".join(str(p) for p in parts)


def _rate_tag(sample_rate: int) -> str:
    if sample_rate >= 1_000_000:
        if sample_rate % 1_000_000 == 0:
            return f"{sample_rate // 1_000_000}M"
        return f"{sample_rate / 1_000_000}M"
    if sample_rate % 1000 == 0:
        return f"{sample_rate // 1000}k"
    return f"{sample_rate}sps"


class Rtl433Decoder:
    RTL433_PATHS = ("rtl_433", "/opt/homebrew/bin/rtl_433", "/usr/local/bin/rtl_433")
    _IGNORED_MODELS = frozenset({"unknown", "Unknown", "console", "log"})

    def __init__(self, freq_mhz: float) -> None:
        self.freq_mhz = freq_mhz
        self._binary = self.find_binary()

    @classmethod
    def find_binary(cls) -> Optional[str]:
        for candidate in cls.RTL433_PATHS:
            path = shutil.which(candidate) if "/" not in candidate else candidate
            if path:
                return path
        return None

    @classmethod
    def soapy_available(cls) -> bool:
        binary = cls.find_binary()
        if not binary:
            return False
        try:
            result = subprocess.run(
                [binary, "-d", "help"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return "SoapySDR device driver is available" in result.stdout

    @property
    def available(self) -> bool:
        return self._binary is not None

    def build_pipe_command(self, sample_rate: int = ISM_SAMPLE_RATE) -> list[str]:
        """Read signed 16-bit IQ from stdin (converted from HackRF cs8)."""
        if not self._binary:
            raise RuntimeError("rtl_433 not found")
        rate = _rate_tag(sample_rate)
        freq = f"{self.freq_mhz:g}M"
        return [
            self._binary,
            "-r",
            f"cs16:{freq}:{rate}:-",
            "-F",
            "json",
            "-M",
            "time:usec",
            "-M",
            "level",
        ]

    def build_sdr_command(self, sample_rate: int = ISM_SAMPLE_RATE) -> list[str]:
        """Direct SoapySDR HackRF input (only when rtl_433 was built with SoapySDR)."""
        if not self._binary:
            raise RuntimeError("rtl_433 not found")
        freq_hz = int(round(self.freq_mhz * 1_000_000))
        return [
            self._binary,
            "-d",
            "driver=hackrf",
            "-f",
            str(freq_hz),
            "-s",
            str(sample_rate),
            "-F",
            "json",
            "-M",
            "time:usec",
            "-M",
            "level",
        ]

    def build_rtlsdr_command(self, sample_rate: int = ISM_SAMPLE_RATE) -> list[str]:
        """Direct rtl_433 + RTL-SDR dongle input."""
        if not self._binary:
            raise RuntimeError("rtl_433 not found")
        freq_hz = int(round(self.freq_mhz * 1_000_000))
        return [
            self._binary,
            "-d",
            "0",
            "-f",
            str(freq_hz),
            "-s",
            str(sample_rate),
            "-F",
            "json",
            "-M",
            "time:usec",
            "-M",
            "level",
        ]

    @staticmethod
    def parse_line(line: str) -> Optional[IsmMessage]:
        line = line.strip()
        if not line or not line.startswith("{"):
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        if "model" not in data:
            return None
        model = str(data["model"])
        if model in Rtl433Decoder._IGNORED_MODELS:
            return None
        timestamp = str(data.get("time", ""))
        level = data.get("rssi")
        if level is not None:
            try:
                level = float(level)
            except (TypeError, ValueError):
                level = None
        frequency = data.get("freq")
        payload = {
            k: v
            for k, v in data.items()
            if k not in {"time", "model", "rssi", "freq", "snr", "noise", "mod"}
        }
        if not payload and level is None:
            return None
        return IsmMessage(
            timestamp=timestamp,
            model=model,
            payload=payload,
            level=level,
            frequency=str(frequency) if frequency is not None else None,
        )
