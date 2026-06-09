from __future__ import annotations

import numpy as np

from satx.dsp.iq import IQConverter


def test_from_rtl_bytes_centers_unsigned_samples():
    data = bytes([0, 255, 127, 128])
    iq = IQConverter.from_rtl_bytes(data)
    assert iq.dtype == np.complex64
    assert iq.shape == (2,)
    assert iq[0] == complex(-127.5, 127.5)
    assert iq[1] == complex(-0.5, 0.5)


def test_from_radio_bytes_uses_backend():
    hackrf = IQConverter.from_radio_bytes(bytes([1, 2]), "hackrf")
    rtl = IQConverter.from_radio_bytes(bytes([1, 2]), "rtlsdr")
    assert hackrf[0] == complex(1.0, 2.0)
    assert rtl[0] == complex(-126.5, -125.5)
