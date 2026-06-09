"""SatX command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from satx import __app_name__, __version__
from satx.app.sniffer import SatXSniffer
from satx.config import SnifferConfig
from satx.config_file import DEFAULT_CONFIG_PATH, ConfigStore, UserConfig
from satx.radio.backends import resolve_backend
from satx.tools.deps import format_missing_warning

BANNER = r"""
 __       _  __  __
/ _\ __ _| |_\ \/ /
\ \ / _` | __|\  / 
_\ \ (_| | |_ /  \ 
\__/\__,_|\__/_/\_\
                   
"""


def build_parser(defaults: UserConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description=(
            f"{__app_name__} v{__version__} — satellite and ISM monitoring for HackRF"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Config file: {DEFAULT_CONFIG_PATH}\n"
            "CLI options override config values.\n"
            "Setup: brew install hackrf && make dev-install"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Path to config JSON (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--file",
        default=defaults.replay_file,
        help="Replay raw HackRF IQ capture instead of live RX",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "hackrf", "rtlsdr"],
        default=defaults.backend,
        help="SDR backend preference (falls back to the other device if unavailable)",
    )
    parser.add_argument(
        "--lna", type=int, default=defaults.lna, help="LNA gain 0-40 dB"
    )
    parser.add_argument(
        "--vga", type=int, default=defaults.vga, help="VGA gain 0-62 dB"
    )
    amp = parser.add_mutually_exclusive_group()
    amp.add_argument(
        "--amp",
        dest="amp_enable",
        action="store_true",
        help="Enable HackRF RF amplifier (+11 dB)",
    )
    amp.add_argument(
        "--no-amp",
        dest="amp_enable",
        action="store_false",
        help="Disable HackRF RF amplifier",
    )
    parser.set_defaults(amp_enable=defaults.amp_enable)
    sound = parser.add_mutually_exclusive_group()
    sound.add_argument(
        "--sound",
        dest="sound_enabled",
        action="store_true",
        help="Enable sound notifications",
    )
    sound.add_argument(
        "--no-sound",
        dest="sound_enabled",
        action="store_false",
        help="Disable sound notifications",
    )
    parser.set_defaults(sound_enabled=defaults.sound_enabled)
    parser.add_argument(
        "--refresh",
        type=float,
        default=defaults.refresh_hz,
        help="Dashboard refresh rate in Hz",
    )
    banner = parser.add_mutually_exclusive_group()
    banner.add_argument(
        "--banner",
        dest="show_banner",
        action="store_true",
        help="Show ASCII banner on startup",
    )
    banner.add_argument(
        "--no-banner",
        dest="show_banner",
        action="store_false",
        help="Skip ASCII banner on startup",
    )
    parser.set_defaults(show_banner=defaults.show_banner)
    return parser


def resolve_config(args: argparse.Namespace, user: UserConfig) -> SnifferConfig:
    base = user.to_sniffer_config()
    return SnifferConfig.from_preset(
        backend=resolve_backend(args.backend),
        lna=args.lna,
        vga=args.vga,
        amp_enable=args.amp_enable,
        tuner_gain=base.radio.tuner_gain,
        ppm_error=base.radio.ppm_error,
        refresh_hz=args.refresh,
        sound_enabled=args.sound_enabled,
        apt_channels=list(base.apt_channels),
        lrpt_channels=list(base.lrpt_channels),
        ism_freq_mhz=base.ism_freq_mhz,
        sat_radio_channels=list(base.sat_radio_channels),
    )


def main(argv: list[str] | None = None) -> None:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=None)
    pre_args, remaining = pre_parser.parse_known_args(argv)
    store = ConfigStore(pre_args.config)
    user_defaults = store.ensure()
    parser = build_parser(user_defaults)
    args = parser.parse_args(remaining)
    if args.config is not None:
        store = ConfigStore(args.config)
        store.ensure()
    if args.show_banner:
        print(BANNER)
    missing = format_missing_warning()
    if missing:
        print(missing, file=sys.stderr)
    user_cfg = store.load()
    config = resolve_config(args, user_cfg)
    sniffer = SatXSniffer(config)
    replay = args.file or user_defaults.replay_file
    if replay:
        sniffer.run_file(replay)
    else:
        sniffer.run_live()


if __name__ == "__main__":
    main(sys.argv[1:])
