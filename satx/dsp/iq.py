"""Convert backend-specific interleaved IQ bytes to complex samples."""

from __future__ import annotations

import numpy as np


class IQConverter:
    @staticmethod
    def from_bytes(data: bytes) -> np.ndarray:
        return IQConverter.from_hackrf_bytes(data)

    @staticmethod
    def from_hackrf_bytes(data: bytes) -> np.ndarray:
        raw = np.frombuffer(data, dtype=np.int8)
        if len(raw) < 2:
            return np.array([], dtype=np.complex64)
        if len(raw) % 2:
            raw = raw[:-1]
        i = raw[0::2].astype(np.float32)
        q = raw[1::2].astype(np.float32)
        return i + 1j * q

    @staticmethod
    def from_rtl_bytes(data: bytes) -> np.ndarray:
        raw = np.frombuffer(data, dtype=np.uint8)
        if len(raw) < 2:
            return np.array([], dtype=np.complex64)
        if len(raw) % 2:
            raw = raw[:-1]
        centered = raw.astype(np.float32) - 127.5
        i = centered[0::2]
        q = centered[1::2]
        return i + 1j * q

    @staticmethod
    def from_radio_bytes(data: bytes, backend: str) -> np.ndarray:
        if backend == "rtlsdr":
            return IQConverter.from_rtl_bytes(data)
        return IQConverter.from_hackrf_bytes(data)
