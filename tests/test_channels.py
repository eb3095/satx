from __future__ import annotations

from satx.apt.channels import parse_apt_channels
from satx.lrpt.channels import parse_lrpt_channels
from satx.radio.channels import parse_sat_radio_channels


def test_default_apt_channels():
    channels = parse_apt_channels(None)
    ids = {ch.channel_id for ch in channels}
    assert "noaa-15" in ids
    assert "noaa-18" in ids
    assert "noaa-19" in ids
    noaa15 = next(ch for ch in channels if ch.channel_id == "noaa-15")
    assert abs(noaa15.freq_mhz - 137.62) < 0.001


def test_default_lrpt_channels():
    channels = parse_lrpt_channels(None)
    assert len(channels) >= 2
    assert all("METEOR" in ch.name for ch in channels)


def test_default_sat_radio_channels():
    channels = parse_sat_radio_channels(None)
    ids = {ch.channel_id for ch in channels}
    assert "iss-voice" in ids
    assert "so-50" in ids
    iss = next(ch for ch in channels if ch.channel_id == "iss-voice")
    assert abs(iss.freq_mhz - 145.8) < 0.001


def test_custom_channel_from_dict():
    custom = [{"id": "test", "name": "Test", "freq_mhz": 137.5, "description": "x"}]
    ch = parse_apt_channels(custom)[0]
    assert ch.channel_id == "test"
    assert ch.freq_hz == 137_500_000
