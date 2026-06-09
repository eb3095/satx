"""IQ spectrum analysis for pass detection and waterfall displays."""

from __future__ import annotations

import numpy as np

FFT_SIZE = 4096
WATERFALL_WIDTH = 512


def analyze_iq_spectrum(
    iq: np.ndarray,
    noise_floor_db: float,
    *,
    fft_size: int = FFT_SIZE,
    width: int = WATERFALL_WIDTH,
    floor_alpha: float = 0.05,
) -> tuple[np.ndarray, float, float, float]:
    """Return spectrum dB band, peak/mean ratio, SNR dB, updated noise floor."""
    if iq.size < fft_size:
        empty = np.array([], dtype=np.float64)
        return empty, 0.0, 0.0, noise_floor_db
    window = iq[:fft_size].astype(np.complex64)
    window *= np.hanning(fft_size).astype(np.float32)
    spectrum = np.abs(np.fft.fftshift(np.fft.fft(window))).astype(np.float64)
    indices = np.linspace(0, spectrum.size - 1, width).astype(int)
    band = spectrum[indices]
    band_db = 20.0 * np.log10(band + 1e-12)
    floor_db = float(np.percentile(band_db, 25))
    noise_floor_db = (1.0 - floor_alpha) * noise_floor_db + floor_alpha * floor_db
    peak_db = float(np.max(band_db))
    snr_db = peak_db - noise_floor_db
    peak_ratio = float(np.max(band) / (np.mean(band) + 1e-12))
    return band_db, peak_ratio, snr_db, noise_floor_db


def spectrum_row(
    spectrum_db: np.ndarray,
    noise_floor_db: float,
    *,
    span_db: float = 12.0,
) -> np.ndarray | None:
    if spectrum_db.size == 0:
        return None
    span = max(span_db, float(np.max(spectrum_db) - noise_floor_db))
    scaled = (spectrum_db - noise_floor_db) / span
    scaled = np.clip(scaled, 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)
