"""NOAA APT WFM monitor with channel selection and pass tracking."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Sequence

import numpy as np

from satx.apt.channels import DEFAULT_APT_CHANNEL_LIST
from satx.config import RadioBackend
from satx.apt.decoder import AptDecoder
from satx.config import APT_CHANNEL_PAGE_SIZE, MAX_APT_EVENTS
from satx.dsp.iq import IQConverter
from satx.dsp.spectrum import FFT_SIZE, analyze_iq_spectrum, spectrum_row
from satx.dsp.wfm_demodulator import WFMDemodulator, demod_wfm
from satx.log_writer import LogWriter

APT_WATERFALL_ROWS = 180
APT_SYNC_PEAK_RATIO = 10.0
APT_SYNC_SNR_DB = 5.0
APT_PASS_END_SEC = 8.0


@dataclass
class AptEvent:
    timestamp: str
    message: str


class AptMonitor:
    def __init__(
        self,
        channels: Sequence = (),
        *,
        radio_backend: RadioBackend = "hackrf",
        log_writer: LogWriter | None = None,
    ) -> None:
        self._log = log_writer
        self._radio_backend = radio_backend
        self._channels = list(channels or DEFAULT_APT_CHANNEL_LIST)
        self.selected_index = 0
        self.page_index = 0
        self._demod = WFMDemodulator()
        self.decoder = AptDecoder()
        self.decoder.channel_name = self.selected_channel().channel_id
        self.signal_level = 0.0
        self.digital_energy = 0.0
        self.sync_hint = False
        self._events: Deque[AptEvent] = deque(maxlen=MAX_APT_EVENTS)
        self._waterfall: Deque[np.ndarray] = deque(maxlen=APT_WATERFALL_ROWS)
        self._noise_floor_db = -55.0
        self._last_decode_at = 0.0
        self._pass_active = False

    @property
    def events(self) -> Deque[AptEvent]:
        return self._events

    @property
    def channels(self) -> List:
        return self._channels

    @property
    def channel_page_size(self) -> int:
        return APT_CHANNEL_PAGE_SIZE

    @property
    def page_count(self) -> int:
        total = len(self.channels)
        return max(1, math.ceil(total / self.channel_page_size)) if total else 1

    def selected_channel(self):
        if not self.channels:
            return DEFAULT_APT_CHANNEL_LIST[0]
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
        self._demod.reset()
        self.decoder.reset()
        self.decoder.channel_name = self.selected_channel().channel_id
        self._reset_metrics()
        return self.selected_channel()

    def channel_up(self):
        return self.select_index(self.selected_index - 1)

    def channel_down(self):
        return self.select_index(self.selected_index + 1)

    def channel_page_up(self) -> None:
        self.page_index = max(0, self.page_index - 1)

    def channel_page_down(self) -> None:
        self.page_index = min(self.page_count - 1, self.page_index + 1)

    def _reset_metrics(self) -> None:
        self.signal_level = 0.0
        self.digital_energy = 0.0
        self.sync_hint = False
        self._waterfall.clear()
        self._noise_floor_db = -55.0
        self._last_decode_at = 0.0
        self._pass_active = False

    def _log_event(self, message: str, now: float) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(now))
        self._events.appendleft(AptEvent(timestamp=stamp, message=message))
        if self._log is not None:
            ch = self.selected_channel()
            self._log.log_apt(f"{stamp} {ch.name} {message}")

    def save_image(self) -> None:
        channel = self.selected_channel()
        path = self.decoder.save_image(channel_name=channel.channel_id, log=self._log)
        if path is not None:
            self._log_event(f"saved {path.name}", time.time())

    def process_iq(self, raw: bytes, now: float | None = None) -> None:
        now = now or time.time()
        iq = IQConverter.from_radio_bytes(raw, self._radio_backend)
        if iq.size == 0:
            return

        prev_lines = self.decoder.line_count
        was_holding = self.decoder.holding_completed_image
        spectrum_db, peak_ratio, snr_db, self._noise_floor_db = analyze_iq_spectrum(
            iq, self._noise_floor_db, fft_size=FFT_SIZE
        )
        self.signal_level = snr_db
        self.digital_energy = peak_ratio

        audio = demod_wfm(iq, demod=self._demod)
        if audio.size:
            self.decoder.process_audio(audio)

        if self.decoder.holding_completed_image and not was_holding:
            self._pass_active = False
            self._log_event("APT image complete — auto-saved", now)

        if self.decoder.line_count > prev_lines:
            self._last_decode_at = now

        decode_active = (
            self._last_decode_at > 0.0
            and now - self._last_decode_at <= APT_PASS_END_SEC
        )
        spectrum_pass = (
            peak_ratio >= APT_SYNC_PEAK_RATIO and snr_db >= APT_SYNC_SNR_DB
        )
        was_pass = self._pass_active
        self.sync_hint = spectrum_pass or decode_active or self.decoder.holding_completed_image
        self._pass_active = self.sync_hint and not self.decoder.holding_completed_image

        if self._pass_active and not was_pass:
            self._log_event(
                f"APT pass detected snr={snr_db:.1f} dB peak/mean={peak_ratio:.1f}",
                now,
            )
        elif was_pass and not self._pass_active and not self.decoder.holding_completed_image:
            self._log_event("APT pass ended", now)

        if self.decoder.line_count > prev_lines and self.decoder.line_count % 250 == 0:
            dec = self.decoder
            self._log_event(
                f"decoding lines={dec.line_count} sync={dec.sync_count} "
                f"audio={dec.signal_level:.3f}",
                now,
            )

        row = spectrum_row(spectrum_db, self._noise_floor_db)
        if row is not None and self.sync_hint:
            self._waterfall.append(row)

    def spectrum_image(self) -> np.ndarray | None:
        if len(self._waterfall) < 2:
            return None
        return np.vstack(list(self._waterfall))
