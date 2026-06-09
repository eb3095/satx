"""METEOR LRPT signal level and sync monitor."""

from __future__ import annotations

import math
import shutil
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, List, Optional, Sequence

import numpy as np
from PIL import Image

from satx.config import MAX_LRPT_EVENTS, RadioBackend
from satx.dsp.iq import IQConverter
from satx.log_writer import LogWriter, default_image_dir, image_save_path
from satx.lrpt.channels import DEFAULT_LRPT_CHANNEL_LIST

from satx.dsp.spectrum import (
    FFT_SIZE,
    WATERFALL_WIDTH,
    analyze_iq_spectrum,
    spectrum_row,
)

LRPT_WATERFALL_ROWS = 180
LRPT_SYNC_PEAK_RATIO = 18.0
LRPT_SYNC_SNR_DB = 8.0


@dataclass
class LrptEvent:
    timestamp: str
    message: str


class LrptMonitor:
    def __init__(
        self,
        channels: Sequence = (),
        *,
        radio_backend: RadioBackend = "hackrf",
        log_writer: LogWriter | None = None,
    ) -> None:
        self._log = log_writer
        self._radio_backend = radio_backend
        self._channels = list(channels or DEFAULT_LRPT_CHANNEL_LIST)
        self.selected_index = 0
        self.page_index = 0
        self.signal_level = 0.0
        self.digital_energy = 0.0
        self.sync_hint = False
        self._events: Deque[LrptEvent] = deque(maxlen=MAX_LRPT_EVENTS)
        self._satdump_available = shutil.which("satdump") is not None
        self._waterfall: Deque[np.ndarray] = deque(maxlen=LRPT_WATERFALL_ROWS)
        self._last_saved: Optional[str] = None
        self.image_dir = default_image_dir()
        self._noise_floor_db = -55.0

    @property
    def satdump_available(self) -> bool:
        return self._satdump_available

    @property
    def last_saved(self) -> Optional[str]:
        return self._last_saved

    @property
    def events(self) -> Deque[LrptEvent]:
        return self._events

    @property
    def channels(self) -> List:
        return self._channels

    @property
    def channel_page_size(self) -> int:
        return 12

    @property
    def page_count(self) -> int:
        total = len(self.channels)
        return max(1, math.ceil(total / self.channel_page_size)) if total else 1

    def selected_channel(self):
        if not self.channels:
            return DEFAULT_LRPT_CHANNEL_LIST[0]
        return self.channels[self.selected_index]

    def page_channels(self) -> List:
        start = self.page_index * self.channel_page_size
        return self.channels[start : start + self.channel_page_size]

    def page_range_label(self) -> str:
        total = len(self.channels)
        if total == 0:
            return "0 channels"
        start = self.page_index * self.channel_page_size
        end = min(start + self.channel_page_size, total)
        return f"{start + 1}–{end} of {total}"

    def select_index(self, index: int):
        if not self.channels:
            self.selected_index = 0
            return self.selected_channel()
        self.selected_index = max(0, min(index, len(self.channels) - 1))
        self.page_index = self.selected_index // self.channel_page_size
        self.signal_level = 0.0
        self.digital_energy = 0.0
        self.sync_hint = False
        self._waterfall.clear()
        self._noise_floor_db = -55.0
        return self.selected_channel()

    def channel_up(self):
        return self.select_index(self.selected_index - 1)

    def channel_down(self):
        return self.select_index(self.selected_index + 1)

    def channel_page_up(self) -> None:
        self.page_index = max(0, self.page_index - 1)

    def channel_page_down(self) -> None:
        self.page_index = min(self.page_count - 1, self.page_index + 1)

    def _log_event(self, message: str, now: float) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(now))
        self._events.appendleft(LrptEvent(timestamp=stamp, message=message))
        if self._log is not None:
            ch = self.selected_channel()
            self._log.log_lrpt(f"{stamp} {ch.name} {message}")

    def process_iq(self, raw: bytes, now: float | None = None) -> None:
        now = now or time.time()
        iq = IQConverter.from_radio_bytes(raw, self._radio_backend)
        if iq.size < FFT_SIZE:
            return
        spectrum_db, peak_ratio, snr_db, self._noise_floor_db = analyze_iq_spectrum(
            iq, self._noise_floor_db, fft_size=FFT_SIZE, width=WATERFALL_WIDTH
        )
        self.signal_level = snr_db
        self.digital_energy = peak_ratio
        was_sync = self.sync_hint
        self.sync_hint = (
            peak_ratio >= LRPT_SYNC_PEAK_RATIO and snr_db >= LRPT_SYNC_SNR_DB
        )
        if self.sync_hint and not was_sync:
            self._log_event(
                f"LRPT pass energy detected snr={snr_db:.1f} dB "
                f"peak/mean={peak_ratio:.1f}",
                now,
            )
        row = spectrum_row(spectrum_db, self._noise_floor_db)
        if row is not None:
            self._waterfall.append(row)

    def current_image(self) -> Optional[np.ndarray]:
        if not self.sync_hint or len(self._waterfall) < 2:
            return None
        return np.vstack(list(self._waterfall))

    def save_image(self) -> Optional[Path]:
        image = self.current_image()
        if image is None:
            return None
        channel = self.selected_channel()
        self.image_dir.mkdir(parents=True, exist_ok=True)
        path = image_save_path(self.image_dir, "lrpt", channel.channel_id)
        Image.fromarray(image, mode="L").save(path)
        self._last_saved = str(path)
        if self._log is not None:
            self._log.log_lrpt(f"saved {path}")
        return path
