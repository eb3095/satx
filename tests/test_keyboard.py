from __future__ import annotations

from unittest.mock import patch

from satx.ui import keyboard
from satx.ui.keyboard import _decode_key, drain_keys, poll_key, reset_pending


def setup_function() -> None:
    reset_pending()


def test_decode_key_dashboards():
    assert _decode_key("A") == "dashboard_apt"
    assert _decode_key("L") == "dashboard_lrpt"
    assert _decode_key("I") == "dashboard_ism"
    assert _decode_key("R") == "dashboard_sat_radio"
    assert _decode_key("s") == "save_image"


def test_decode_key_radio_controls():
    assert _decode_key("[") == "prev"
    assert _decode_key("]") == "next"
    assert _decode_key("\x1b[A") == "channel_up"
    assert _decode_key("\x03") == "quit"


def test_poll_key_and_drain():
    keyboard._pending = ""
    with patch("satx.ui.keyboard.sys.stdin.isatty", return_value=True):
        with patch(
            "satx.ui.keyboard.select.select",
            side_effect=[([object()], [], []), ([], [], [])],
        ):
            with patch("satx.ui.keyboard._read_available", side_effect=["L", ""]):
                assert poll_key() == "dashboard_lrpt"
                assert drain_keys() == []
