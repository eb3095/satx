from __future__ import annotations

from pathlib import Path

from satx.apt.decoder import AptDecoder, synthetic_apt_audio


def test_apt_decoder_detects_synthetic_sync(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SATX_IMAGE_DIR", str(tmp_path))
    decoder = AptDecoder()
    audio = synthetic_apt_audio(line_count=6)
    decoder.process_audio(audio)
    assert decoder.sync_count >= 4
    assert decoder.line_count >= 4
    assert decoder.signal_level > 0.0


def test_apt_decoder_save_image_incomplete(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SATX_IMAGE_DIR", str(tmp_path))
    decoder = AptDecoder()
    audio = synthetic_apt_audio(line_count=3)
    decoder.process_audio(audio)
    assert decoder.save_image(channel_name="noaa-19") is None


def test_apt_decoder_auto_save_holds_image_until_next_pass(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("SATX_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr("satx.apt.decoder.APT_IMAGE_COMPLETE_LINES", 3)
    decoder = AptDecoder()
    decoder.channel_name = "noaa-19"
    import numpy as np

    from satx.apt.decoder import APT_LINE_WIDTH

    decoder._lines = [np.zeros(APT_LINE_WIDTH, dtype=np.uint8) for _ in range(3)]
    decoder._line_count = 3
    path = decoder.save_image(channel_name="noaa-19", auto=True)
    assert path is not None
    assert decoder.line_count == 0
    held = decoder.current_image()
    assert held is not None
    assert held.shape[0] == 3
    decoder.process_audio(synthetic_apt_audio(line_count=1))
    assert decoder.current_image() is not None
    assert not decoder.holding_completed_image


def test_apt_decoder_save_image(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SATX_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr("satx.apt.decoder.APT_IMAGE_COMPLETE_LINES", 3)
    decoder = AptDecoder()
    decoder.channel_name = "noaa-19"
    import numpy as np

    from satx.apt.decoder import APT_LINE_WIDTH

    decoder._lines = [np.zeros(APT_LINE_WIDTH, dtype=np.uint8) for _ in range(3)]
    decoder._line_count = 3
    path = decoder.save_image(channel_name="noaa-19")
    assert path is not None
    assert path.exists()
    assert path.suffix == ".png"
    assert path.name.startswith("apt_noaa-19_")
    assert path.parent == tmp_path
