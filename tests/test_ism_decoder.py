from __future__ import annotations

from satx.config import ISM_SAMPLE_RATE
from satx.ism.decoder import Rtl433Decoder


def test_rtl433_parse_json_line():
    line = (
        '{"time":"2026-06-08 12:00:00","model":"Fineoffset-WH65B","id":42,'
        '"temperature_F":72.5,"humidity":55,"rssi":-12}'
    )
    msg = Rtl433Decoder.parse_line(line)
    assert msg is not None
    assert msg.model == "Fineoffset-WH65B"
    assert msg.payload["id"] == 42
    assert msg.payload["temperature_F"] == 72.5
    assert msg.level == -12.0


def test_rtl433_parse_invalid_line():
    assert Rtl433Decoder.parse_line("not json") is None
    assert Rtl433Decoder.parse_line("") is None
    assert (
        Rtl433Decoder.parse_line('{"time":"now","message":"Use \\"-F log\\""}') is None
    )


def test_rtl433_rejects_meta_without_model():
    assert Rtl433Decoder.parse_line('{"time":"now","level":1}') is None


def test_rtl433_build_pipe_command():
    dec = Rtl433Decoder(433.92)
    if dec.available:
        cmd = dec.build_pipe_command(ISM_SAMPLE_RATE)
        assert "rtl_433" in cmd[0] or cmd[0].endswith("rtl_433")
        assert f"cs16:433.92M:2M:-" in cmd
        assert "json" in cmd


def test_rtl433_build_sdr_command():
    dec = Rtl433Decoder(433.92)
    if dec.available:
        cmd = dec.build_sdr_command(ISM_SAMPLE_RATE)
        assert "driver=hackrf" in cmd
        assert "433920000" in cmd


def test_rtl433_build_rtlsdr_command():
    dec = Rtl433Decoder(433.92)
    if dec.available:
        cmd = dec.build_rtlsdr_command(ISM_SAMPLE_RATE)
        assert "-d" in cmd
        assert "0" in cmd
        assert "433920000" in cmd
