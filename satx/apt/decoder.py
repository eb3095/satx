"""NOAA APT line sync detection and grayscale image assembly."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

from satx.config import APT_AUDIO_RATE
from satx.log_writer import LogWriter, default_image_dir, image_save_path

APT_SYNC_FREQ = 2400.0
APT_LINE_RATE = 2.0
APT_LINE_WIDTH = 909
APT_SYNC_WINDOW = int(0.02 * APT_AUDIO_RATE)
APT_LINE_SAMPLES = int(APT_AUDIO_RATE / APT_LINE_RATE)
APT_MIN_SYNC_ENERGY = 0.08
APT_IMAGE_COMPLETE_LINES = 2000


def _goertzel_energy(samples: np.ndarray, sample_rate: float, freq: float) -> float:
    if samples.size == 0:
        return 0.0
    n = samples.size
    k = int(0.5 + (n * freq) / sample_rate)
    w = (2.0 * np.pi / n) * k
    cosine = np.cos(w)
    sine = np.sin(w)
    coeff = 2.0 * cosine
    s_prev = 0.0
    s_prev2 = 0.0
    for sample in samples.astype(np.float64):
        s = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s
    power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
    return float(power / (n * n))


def _extract_line_pixels(line_audio: np.ndarray) -> np.ndarray:
    if line_audio.size < APT_LINE_WIDTH:
        return np.zeros(APT_LINE_WIDTH, dtype=np.uint8)
    video = line_audio[APT_SYNC_WINDOW:]
    if video.size < APT_LINE_WIDTH:
        pad = APT_LINE_WIDTH - video.size
        video = np.pad(video, (0, pad))
    indices = np.linspace(0, video.size - 1, APT_LINE_WIDTH).astype(int)
    picked = np.abs(video[indices].astype(np.float64))
    picked -= picked.min()
    peak = picked.max()
    if peak > 1e-9:
        picked = picked / peak
    return (picked * 255.0).astype(np.uint8)


@dataclass
class AptDecoder:
    sample_rate: int = APT_AUDIO_RATE
    image_dir: Path = field(default_factory=default_image_dir)
    _lines: List[np.ndarray] = field(default_factory=list, init=False)
    _line_count: int = field(default=0, init=False)
    _sync_count: int = field(default=0, init=False)
    _carry: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.float32), init=False
    )
    _last_sync_at: float = field(default=0.0, init=False)
    _signal_level: float = field(default=0.0, init=False)
    _last_saved: Optional[str] = field(default=None, init=False)
    _channel_name: str = field(default="apt", init=False)
    _held_image: Optional[np.ndarray] = field(default=None, init=False)

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @channel_name.setter
    def channel_name(self, value: str) -> None:
        self._channel_name = value or "apt"

    @property
    def line_count(self) -> int:
        return self._line_count

    @property
    def sync_count(self) -> int:
        return self._sync_count

    @property
    def signal_level(self) -> float:
        return self._signal_level

    @property
    def last_saved(self) -> Optional[str]:
        return self._last_saved

    @property
    def image_complete(self) -> bool:
        return self._line_count >= APT_IMAGE_COMPLETE_LINES

    @property
    def holding_completed_image(self) -> bool:
        return self._held_image is not None and not self._lines

    def reset(self) -> None:
        self._clear_accumulator()
        self._held_image = None
        self._last_saved = None

    def _clear_accumulator(self) -> None:
        self._lines = []
        self._line_count = 0
        self._sync_count = 0
        self._carry = np.array([], dtype=np.float32)
        self._last_sync_at = 0.0
        self._signal_level = 0.0

    def process_audio(self, audio: np.ndarray) -> None:
        if audio.size == 0:
            return
        buf = np.concatenate([self._carry, audio.astype(np.float32)])
        self._signal_level = float(np.sqrt(np.mean(buf * buf)))
        while buf.size >= APT_LINE_SAMPLES:
            chunk = buf[:APT_LINE_SAMPLES]
            buf = buf[APT_LINE_SAMPLES:]
            sync_slice = chunk[:APT_SYNC_WINDOW]
            energy = _goertzel_energy(sync_slice, self.sample_rate, APT_SYNC_FREQ)
            if energy >= APT_MIN_SYNC_ENERGY:
                if self._held_image is not None and not self._lines:
                    self._held_image = None
                self._sync_count += 1
                pixels = _extract_line_pixels(chunk)
                self._lines.append(pixels)
                self._line_count += 1
                self._last_sync_at = time.time()
                if self.image_complete:
                    self.save_image(auto=True, channel_name=self._channel_name)
        self._carry = buf

    def preview_lines(self, count: int = 8) -> List[np.ndarray]:
        if not self._lines:
            return []
        return self._lines[-count:]

    def current_image(self) -> Optional[np.ndarray]:
        if self._lines:
            return np.vstack(self._lines)
        if self._held_image is not None:
            return self._held_image
        return None

    def save_image(
        self,
        *,
        channel_name: str = "apt",
        auto: bool = False,
        log: LogWriter | None = None,
    ) -> Optional[Path]:
        if not self._lines or not self.image_complete:
            return None
        self.image_dir.mkdir(parents=True, exist_ok=True)
        image = np.vstack(self._lines)
        path = image_save_path(self.image_dir, "apt", channel_name)
        Image.fromarray(image, mode="L").save(path)
        self._last_saved = str(path)
        if log is not None:
            log.log_apt(f"saved {path} lines={self._line_count}")
        if auto:
            self._held_image = image
            self._clear_accumulator()
        return path


def synthetic_apt_audio(
    *,
    sample_rate: int = APT_AUDIO_RATE,
    line_count: int = 4,
    sync_ms: float = 20.0,
) -> np.ndarray:
    """Generate APT-like audio with 2400 Hz sync bursts for unit tests."""
    line_samples = int(sample_rate / APT_LINE_RATE)
    sync_samples = int(sync_ms * sample_rate / 1000.0)
    t_sync = np.arange(sync_samples, dtype=np.float64) / sample_rate
    sync_tone = 0.9 * np.sin(2.0 * np.pi * APT_SYNC_FREQ * t_sync)
    parts: List[np.ndarray] = []
    for _ in range(line_count):
        line = np.zeros(line_samples, dtype=np.float32)
        line[:sync_samples] = sync_tone.astype(np.float32)
        video = np.linspace(0.2, 0.8, line_samples - sync_samples, dtype=np.float32)
        line[sync_samples:] = video
        parts.append(line)
    return np.concatenate(parts)
