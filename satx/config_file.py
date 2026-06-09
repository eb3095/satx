"""Persistent user configuration at ~/.config/satx/config.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, List, Optional

from satx.apt.channel_defaults import DEFAULT_APT_CHANNELS
from satx.apt.channels import parse_apt_channels
from satx.config import ISM_DEFAULT_FREQ_MHZ, RadioBackend, SnifferConfig
from satx.lrpt.channel_defaults import DEFAULT_LRPT_CHANNELS
from satx.lrpt.channels import parse_lrpt_channels
from satx.radio.channel_defaults import DEFAULT_SAT_RADIO_CHANNELS
from satx.radio.channels import parse_sat_radio_channels

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "satx"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class UserConfig:
    backend: str = "auto"
    lna: int = 32
    vga: int = 48
    amp_enable: bool = True
    tuner_gain: int = 40
    ppm_error: int = 0
    sound_enabled: bool = True
    refresh_hz: float = 2.0
    show_banner: bool = True
    replay_file: Optional[str] = None
    apt_channels: Optional[List[dict[str, Any]]] = None
    lrpt_channels: Optional[List[dict[str, Any]]] = None
    ism_freq_mhz: float = ISM_DEFAULT_FREQ_MHZ
    sat_radio_channels: Optional[List[dict[str, Any]]] = None

    @classmethod
    def defaults(cls) -> UserConfig:
        return cls(
            apt_channels=[dict(ch) for ch in DEFAULT_APT_CHANNELS],
            lrpt_channels=[dict(ch) for ch in DEFAULT_LRPT_CHANNELS],
            sat_radio_channels=[dict(ch) for ch in DEFAULT_SAT_RADIO_CHANNELS],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserConfig:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_sniffer_config(self) -> SnifferConfig:
        from satx.radio.backends import resolve_backend

        return SnifferConfig.from_preset(
            backend=resolve_backend(self.backend),  # type: ignore[arg-type]
            lna=self.lna,
            vga=self.vga,
            amp_enable=self.amp_enable,
            tuner_gain=self.tuner_gain,
            ppm_error=self.ppm_error,
            refresh_hz=self.refresh_hz,
            sound_enabled=self.sound_enabled,
            apt_channels=parse_apt_channels(self.apt_channels),
            lrpt_channels=parse_lrpt_channels(self.lrpt_channels),
            ism_freq_mhz=self.ism_freq_mhz,
            sat_radio_channels=parse_sat_radio_channels(self.sat_radio_channels),
        )


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CONFIG_PATH

    def ensure(self) -> UserConfig:
        if not self.path.exists():
            self.write(UserConfig.defaults())
        return self.load()

    def load(self) -> UserConfig:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a JSON object: {self.path}")
        return UserConfig.from_dict(raw)

    def write(self, config: UserConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config.to_dict(), indent=2, sort_keys=True)
        self.path.write_text(payload + "\n", encoding="utf-8")
