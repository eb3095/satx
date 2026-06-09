"""Radio receiver factory for supported SDR backends."""

from __future__ import annotations

from typing import Protocol

from satx.config import SAMPLE_RATE, RadioConfig
from satx.radio.hackrf import HackRFReceiver
from satx.radio.rtlsdr import RtlSdrReceiver


class RadioReceiver(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def set_frequency(self, freq_hz: int) -> None: ...

    def read_chunk(self, timeout: float = 0.05) -> bytes: ...

    @property
    def running(self) -> bool: ...

    @property
    def exited(self) -> bool: ...

    def exit_error(self) -> str | None: ...


def make_receiver(
    config: RadioConfig,
    *,
    freq_hz: int,
    sample_rate: int = SAMPLE_RATE,
) -> RadioReceiver:
    if config.backend == "rtlsdr":
        return RtlSdrReceiver(config, freq_hz=freq_hz, sample_rate=sample_rate)
    return HackRFReceiver(config, freq_hz=freq_hz, sample_rate=sample_rate)
