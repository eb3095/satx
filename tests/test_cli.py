from __future__ import annotations

from satx.app.cli import build_parser, resolve_config
from satx.config_file import UserConfig


def test_cli_overrides_config_defaults():
    defaults = UserConfig(lna=32, vga=48)
    parser = build_parser(defaults)
    args = parser.parse_args(["--lna", "24", "--vga", "40", "--no-sound"])
    cfg = resolve_config(args, defaults)
    assert cfg.radio.lna_gain == 24
    assert cfg.radio.vga_gain == 40
    assert cfg.sound_enabled is False
    assert cfg.radio.backend == "hackrf"


def test_cli_uses_config_when_no_overrides():
    defaults = UserConfig(
        backend="rtlsdr",
        lna=40,
        vga=50,
        tuner_gain=35,
        ppm_error=2,
    )
    parser = build_parser(defaults)
    args = parser.parse_args([])
    cfg = resolve_config(args, defaults)
    assert cfg.radio.lna_gain == 40
    assert cfg.radio.vga_gain == 50
    assert cfg.radio.backend == "rtlsdr"
    assert cfg.radio.tuner_gain == 35
    assert cfg.radio.ppm_error == 2
