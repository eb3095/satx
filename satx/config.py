"""Runtime configuration and RF constants for SatX."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

SAMPLE_RATE = 2_000_000
CHUNK_SAMPLES = 256 * 1024

APT_AUDIO_RATE = 8_000
APT_CHANNEL_PAGE_SIZE = 12
LRPT_CHANNEL_PAGE_SIZE = 12

SAT_AUDIO_RATE = 16_000
SAT_VOLUME_DEFAULT = 3.0
SAT_VOLUME_MIN = 0.0
SAT_VOLUME_MAX = 12.0
SAT_VOLUME_STEP = 0.25
WAVEFORM_HEIGHT = 7
SAT_RADIO_CHANNEL_PAGE_SIZE = 15

MAX_RADIO_TRANSCRIPTS = 50
MAX_ISM_MESSAGES = 200
MAX_LRPT_EVENTS = 100
MAX_APT_EVENTS = 100

APT_DEFAULT_FREQ_HZ = 137_620_000
LRPT_DEFAULT_FREQ_HZ = 137_900_000
ISM_DEFAULT_FREQ_MHZ = 433.92
ISM_SAMPLE_RATE = 2_000_000
SAT_DEFAULT_FREQ_HZ = 145_800_000

HACKRF_BINARY_PATHS = (
    "hackrf_transfer",
    "/opt/homebrew/bin/hackrf_transfer",
    "/usr/local/bin/hackrf_transfer",
)
RTL_SDR_BINARY_PATHS = (
    "rtl_sdr",
    "/opt/homebrew/bin/rtl_sdr",
    "/usr/local/bin/rtl_sdr",
)

RadioBackend = Literal["hackrf", "rtlsdr"]


@dataclass(frozen=True)
class RadioConfig:
    backend: RadioBackend = "hackrf"
    lna_gain: int = 24
    vga_gain: int = 40
    amp_enable: bool = True
    tuner_gain: int = 40
    ppm_error: int = 0


@dataclass(frozen=True)
class SatChannel:
    channel_id: str
    name: str
    freq_hz: int
    description: str

    @property
    def freq_mhz(self) -> float:
        return self.freq_hz / 1_000_000


@dataclass(frozen=True)
class SnifferConfig:
    radio: RadioConfig = RadioConfig()
    refresh_hz: float = 2.0
    sound_enabled: bool = True
    apt_channels: Tuple[SatChannel, ...] = ()
    lrpt_channels: Tuple[SatChannel, ...] = ()
    ism_freq_mhz: float = ISM_DEFAULT_FREQ_MHZ
    sat_radio_channels: Tuple[SatChannel, ...] = ()

    @classmethod
    def from_preset(
        cls,
        *,
        backend: RadioBackend = "hackrf",
        lna: int = 24,
        vga: int = 40,
        amp_enable: bool = True,
        tuner_gain: int = 40,
        ppm_error: int = 0,
        refresh_hz: float = 2.0,
        sound_enabled: bool = True,
        apt_channels: Optional[List[SatChannel]] = None,
        lrpt_channels: Optional[List[SatChannel]] = None,
        ism_freq_mhz: float = ISM_DEFAULT_FREQ_MHZ,
        sat_radio_channels: Optional[List[SatChannel]] = None,
    ) -> SnifferConfig:
        return cls(
            radio=RadioConfig(
                backend=backend,
                lna_gain=lna,
                vga_gain=vga,
                amp_enable=amp_enable,
                tuner_gain=tuner_gain,
                ppm_error=ppm_error,
            ),
            refresh_hz=refresh_hz,
            sound_enabled=sound_enabled,
            apt_channels=tuple(apt_channels or ()),
            lrpt_channels=tuple(lrpt_channels or ()),
            ism_freq_mhz=ism_freq_mhz,
            sat_radio_channels=tuple(sat_radio_channels or ()),
        )
