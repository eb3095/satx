"""Satellite NBFM voice monitor and per-channel transcripts."""

from __future__ import annotations

import math
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Sequence

import numpy as np

from satx.config import (
    MAX_RADIO_TRANSCRIPTS,
    RadioBackend,
    SAT_RADIO_CHANNEL_PAGE_SIZE,
    SAT_VOLUME_DEFAULT,
    SAT_VOLUME_MAX,
    SAT_VOLUME_MIN,
    SAT_VOLUME_STEP,
)
from satx.dsp.iq import IQConverter
from satx.dsp.nbfm_demodulator import NBFMDemodulator, demod_nbfm
from satx.dsp.waveform import WaveformScope
from satx.log_writer import LogWriter
from satx.radio.audio_output import AudioOutput
from satx.radio.channels import DEFAULT_SAT_CHANNELS
from satx.radio.speech_segmenter import SpeechSegmenter
from satx.radio.squelch import SquelchGate
from satx.radio.transcriber import SpeechTranscriber, create_transcriber


@dataclass
class TranscriptLine:
    timestamp: str
    text: str
    channel_id: str


class VoiceMonitor:
    def __init__(
        self,
        channels: Sequence = (),
        *,
        radio_backend: RadioBackend = "hackrf",
        log_writer: LogWriter | None = None,
    ) -> None:
        self._log = log_writer
        self._radio_backend = radio_backend
        self._channels = list(channels or DEFAULT_SAT_CHANNELS)
        self.selected_index = 0
        self.page_index = 0
        self.squelch = SquelchGate()
        self.volume = SAT_VOLUME_DEFAULT
        self._demod = NBFMDemodulator()
        self._segmenter = SpeechSegmenter(squelch=self.squelch)
        self._waveform = WaveformScope()
        self._audio_out = AudioOutput()
        self._gate_open = False
        self._buffers: Dict[str, Deque[TranscriptLine]] = {
            ch.channel_id: deque(maxlen=MAX_RADIO_TRANSCRIPTS) for ch in self._channels
        }
        self._queue: queue.Queue[tuple[str, np.ndarray, float]] = queue.Queue()
        self._transcriber: SpeechTranscriber | None = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        threading.Thread(target=self._load_transcriber, daemon=True).start()

    def _load_transcriber(self) -> None:
        self._transcriber = create_transcriber()

    @property
    def channels(self) -> List:
        return self._channels

    @property
    def channel_page_size(self) -> int:
        return SAT_RADIO_CHANNEL_PAGE_SIZE

    @property
    def page_count(self) -> int:
        total = len(self.channels)
        return max(1, math.ceil(total / self.channel_page_size)) if total else 1

    @property
    def transcriber_status(self) -> str:
        if self._transcriber is None:
            return "loading"
        return self._transcriber.status

    @property
    def stt_available(self) -> bool:
        return self._transcriber is not None and self._transcriber.available

    @property
    def audio_available(self) -> bool:
        return self._audio_out.available

    @property
    def waveform(self) -> WaveformScope:
        return self._waveform

    @property
    def gate_open(self) -> bool:
        return self._gate_open

    def selected_channel(self):
        if not self.channels:
            return DEFAULT_SAT_CHANNELS[0]
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
        self._segmenter = SpeechSegmenter(squelch=self.squelch)
        self._waveform = WaveformScope()
        self._demod.reset()
        self.squelch.reset_calibration()
        return self.selected_channel()

    def channel_up(self):
        return self.select_index(self.selected_index - 1)

    def channel_down(self):
        return self.select_index(self.selected_index + 1)

    def channel_page_up(self) -> None:
        self.page_index = max(0, self.page_index - 1)

    def channel_page_down(self) -> None:
        self.page_index = min(self.page_count - 1, self.page_index + 1)

    def volume_up(self) -> float:
        self.volume = min(SAT_VOLUME_MAX, self.volume + SAT_VOLUME_STEP)
        return self.volume

    def volume_down(self) -> float:
        self.volume = max(SAT_VOLUME_MIN, self.volume - SAT_VOLUME_STEP)
        return self.volume

    def squelch_up(self) -> float:
        return self.squelch.adjust(self.squelch.step_db)

    def squelch_down(self) -> float:
        return self.squelch.adjust(-self.squelch.step_db)

    def buffer_for(self, channel_id: str | None = None) -> Deque[TranscriptLine]:
        cid = channel_id or self.selected_channel().channel_id
        if cid not in self._buffers:
            self._buffers[cid] = deque(maxlen=MAX_RADIO_TRANSCRIPTS)
        return self._buffers[cid]

    def process_iq(self, raw: bytes, now: float | None = None) -> None:
        now = now or time.time()
        iq = IQConverter.from_radio_bytes(raw, self._radio_backend)
        if iq.size == 0:
            return
        audio = demod_nbfm(iq, demod=self._demod)
        if audio.size == 0:
            return
        gated, _, self._gate_open = self.squelch.gate_audio(audio, now=time.monotonic())
        self._waveform.feed(audio)
        loud = np.clip(gated * self.volume, -1.0, 1.0)
        self._audio_out.write(loud)
        channel = self.selected_channel()
        for segment in self._segmenter.feed(audio):
            self._queue.put((channel.channel_id, segment, now))

    def _freq_mhz_for(self, channel_id: str) -> float | None:
        for channel in self.channels:
            if channel.channel_id == channel_id:
                return channel.freq_mhz
        return None

    def _worker_loop(self) -> None:
        while True:
            channel_id, audio, now = self._queue.get()
            try:
                while self._transcriber is None:
                    time.sleep(0.05)
                text = self._transcriber.transcribe(audio)
                if not text:
                    continue
                line = TranscriptLine(
                    timestamp=time.strftime("%H:%M:%S", time.localtime(now)),
                    text=text,
                    channel_id=channel_id,
                )
                self._buffers[channel_id].append(line)
                if self._log is not None:
                    freq_mhz = self._freq_mhz_for(channel_id)
                    if freq_mhz is not None:
                        self._log.log_radio_transcript(freq_mhz, text)
            finally:
                self._queue.task_done()

    def shutdown(self) -> None:
        self._audio_out.shutdown()
