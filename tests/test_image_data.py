from __future__ import annotations

import numpy as np

from satx.apt.decoder import AptDecoder, synthetic_apt_audio


def test_current_image_stacks_lines():
    dec = AptDecoder()
    dec.process_audio(synthetic_apt_audio(line_count=3))
    image = dec.current_image()
    assert image is not None
    assert image.ndim == 2
    assert image.shape[0] >= 3


def test_lrpt_waterfall_image():
    from satx.lrpt.monitor import LrptMonitor

    monitor = LrptMonitor()
    raw = np.zeros(256 * 1024 * 2, dtype=np.int8)
    for _ in range(5):
        monitor.process_iq(raw.tobytes())
    assert monitor.current_image() is None
    assert len(monitor._waterfall) >= 1
    assert monitor._waterfall[0].shape[0] == 512


def test_lrpt_image_only_when_synced():
    from satx.lrpt.monitor import LrptMonitor

    monitor = LrptMonitor()
    monitor.sync_hint = True
    monitor._waterfall.append(np.zeros(512, dtype=np.uint8))
    monitor._waterfall.append(np.ones(512, dtype=np.uint8) * 128)
    image = monitor.current_image()
    assert image is not None
