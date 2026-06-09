"""Narrowband FM demodulation for satellite voice channels."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from satx.config import SAMPLE_RATE, SAT_AUDIO_RATE


def _boxcar_decimate_complex(samples: np.ndarray, factor: int) -> np.ndarray:
    count = (samples.size // factor) * factor
    if count == 0:
        return np.array([], dtype=np.complex64)
    return samples[:count].reshape(-1, factor).mean(axis=1).astype(np.complex64)


def _boxcar_decimate_real(samples: np.ndarray, factor: int) -> np.ndarray:
    count = (samples.size // factor) * factor
    if count == 0:
        return np.array([], dtype=np.float64)
    return samples[:count].reshape(-1, factor).mean(axis=1)


_IQ_DECIM = 25
_AUDIO_DECIM = 5
_TOTAL_DECIM = _IQ_DECIM * _AUDIO_DECIM


@dataclass
class NBFMDemodulator:
    agc_gain: float = field(default=1.0, init=False)
    _agc_min: float = 0.02
    _agc_max: float = 80.0
    _target_rms: float = 0.18
    _prev_sample: complex = field(default=1 + 0j, init=False)

    def reset(self) -> None:
        self.agc_gain = 1.0
        self._prev_sample = 1 + 0j

    def _discriminator(self, iq: np.ndarray) -> np.ndarray:
        if iq.size < 1:
            return np.array([], dtype=np.float32)
        z = np.concatenate(([self._prev_sample], iq))
        fm = 0.5 * np.angle(z[:-1] * np.conj(z[1:]))
        self._prev_sample = complex(iq[-1])
        return fm.astype(np.float32)

    def demod(
        self,
        iq: np.ndarray,
        sample_rate: int = SAMPLE_RATE,
        audio_rate: int = SAT_AUDIO_RATE,
    ) -> np.ndarray:
        if iq.size == 0:
            return np.array([], dtype=np.float32)
        expected_decim = max(1, sample_rate // audio_rate)
        iq_decim = (
            _IQ_DECIM if expected_decim == _TOTAL_DECIM else max(1, expected_decim // 5)
        )
        audio_decim = max(1, expected_decim // iq_decim)
        scaled = iq.astype(np.complex64) / 128.0
        narrow = _boxcar_decimate_complex(scaled, iq_decim)
        if narrow.size == 0:
            return np.array([], dtype=np.float32)
        fm = self._discriminator(narrow)
        audio = _boxcar_decimate_real(fm.astype(np.float64), audio_decim)
        if audio.size == 0:
            return np.array([], dtype=np.float32)
        audio -= np.mean(audio)
        rms = float(np.sqrt(np.mean(audio * audio)))
        if rms > 1e-9:
            desired = self._target_rms / rms
            if desired < self.agc_gain:
                self.agc_gain = 0.3 * self.agc_gain + 0.7 * desired
            else:
                self.agc_gain = 0.97 * self.agc_gain + 0.03 * desired
            self.agc_gain = float(np.clip(self.agc_gain, self._agc_min, self._agc_max))
        out = np.clip(audio * self.agc_gain, -1.0, 1.0)
        return out.astype(np.float32)


def demod_nbfm(
    iq: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    audio_rate: int = SAT_AUDIO_RATE,
    *,
    demod: NBFMDemodulator | None = None,
) -> np.ndarray:
    engine = NBFMDemodulator() if demod is None else demod
    return engine.demod(iq, sample_rate=sample_rate, audio_rate=audio_rate)
