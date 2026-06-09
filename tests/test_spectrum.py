from __future__ import annotations

import numpy as np

from satx.dsp.spectrum import analyze_iq_spectrum, spectrum_row


def test_analyze_iq_spectrum_returns_metrics():
    iq = np.exp(1j * np.linspace(0, 20, 4096)).astype(np.complex64)
    band_db, peak_ratio, snr_db, floor = analyze_iq_spectrum(iq, -55.0)
    assert band_db.size > 0
    assert peak_ratio > 1.0
    assert snr_db > 0.0
    row = spectrum_row(band_db, floor)
    assert row is not None
    assert row.dtype == np.uint8
