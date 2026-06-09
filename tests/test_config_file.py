from __future__ import annotations

import json
from pathlib import Path

from satx.config_file import ConfigStore, UserConfig


def test_user_config_defaults():
    cfg = UserConfig.defaults()
    assert cfg.backend == "hackrf"
    assert cfg.lna == 32
    assert cfg.vga == 48
    assert cfg.tuner_gain == 40
    assert cfg.ppm_error == 0
    assert cfg.sound_enabled is True
    assert cfg.ism_freq_mhz == 433.92


def test_user_config_round_trip():
    cfg = UserConfig(lna=24, vga=40, ism_freq_mhz=433.5)
    restored = UserConfig.from_dict(cfg.to_dict())
    assert restored.lna == 24
    assert restored.vga == 40
    assert restored.ism_freq_mhz == 433.5


def test_config_store_creates_default_file(tmp_path: Path):
    path = tmp_path / "satx" / "config.json"
    store = ConfigStore(path)
    cfg = store.ensure()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["show_banner"] is True
    assert cfg.show_banner is True
    assert "lat" not in data
    assert "lon" not in data


def test_to_sniffer_config_has_all_dashboards():
    cfg = UserConfig.defaults()
    sn = cfg.to_sniffer_config()
    assert len(sn.apt_channels) >= 3
    assert len(sn.lrpt_channels) >= 2
    assert len(sn.sat_radio_channels) >= 6
    assert sn.ism_freq_mhz == 433.92
    assert sn.radio.backend == "hackrf"
    assert sn.radio.tuner_gain == 40
    assert sn.radio.ppm_error == 0
