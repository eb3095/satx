"""Braille oscilloscope waveform for radio dashboard."""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Tuple

import numpy as np
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from satx.config import WAVEFORM_HEIGHT

_BRAILLE_DOTS: Tuple[Tuple[int, int, int], ...] = (
    (0, 0, 0x01),
    (1, 0, 0x08),
    (0, 1, 0x02),
    (1, 1, 0x10),
    (0, 2, 0x04),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)


class WaveformScope:
    def __init__(self, *, columns: int = 120) -> None:
        self._columns = columns
        self._samples: Deque[float] = deque(maxlen=columns * 8)

    def feed(self, audio: np.ndarray) -> None:
        if audio.size == 0:
            return
        mono = audio.astype(np.float32)
        step = max(1, mono.size // 64)
        for idx in range(0, mono.size, step):
            self._samples.append(float(mono[idx]))

    def _resample(self, count: int) -> np.ndarray:
        if count <= 0:
            return np.zeros(0, dtype=np.float32)
        if not self._samples:
            return np.zeros(count, dtype=np.float32)
        src = np.asarray(self._samples, dtype=np.float32)
        if src.size == 1:
            return np.full(count, src[0], dtype=np.float32)
        x_src = np.linspace(0.0, 1.0, src.size, dtype=np.float64)
        x_dst = np.linspace(0.0, 1.0, count, dtype=np.float64)
        return np.interp(x_dst, x_src, src).astype(np.float32)

    def _prepare_trace(self, width_px: int) -> np.ndarray:
        trace = self._resample(width_px)
        if trace.size == 0:
            return trace
        trace = trace - float(np.mean(trace))
        peak = float(np.max(np.abs(trace)))
        if peak > 1e-8:
            trace = trace / peak
        return np.clip(trace, -1.0, 1.0)

    def render_lines(
        self,
        *,
        width_chars: int,
        height_chars: int = WAVEFORM_HEIGHT,
        gate_open: bool = False,
    ) -> List[Text]:
        width_chars = max(16, width_chars)
        height_chars = max(4, height_chars)
        grid_w = width_chars * 2
        grid_h = height_chars * 4
        wave = [[0] * grid_w for _ in range(grid_h)]
        grid = [[0] * grid_w for _ in range(grid_h)]
        mid = (grid_h - 1) / 2.0
        for gx in range(grid_w):
            grid[int(round(mid))][gx] |= 0x01
        trace = self._prepare_trace(grid_w)
        if trace.size:
            for gx, sample in enumerate(trace):
                y = int(round((1.0 - (sample + 1.0) * 0.5) * (grid_h - 1)))
                y = max(0, min(grid_h - 1, y))
                wave[y][gx] |= 0x02
        wave_style = "bold bright_green" if gate_open else "dim"
        grid_style = "dim green" if gate_open else "dim"
        rows: List[Text] = []
        for row in range(0, grid_h, 4):
            line = Text()
            for col in range(0, grid_w, 2):
                wave_bits = 0
                grid_bits = 0
                for dx, dy, bit in _BRAILLE_DOTS:
                    gx, gy = col + dx, row + dy
                    if gy >= grid_h or gx >= grid_w:
                        continue
                    if wave[gy][gx]:
                        wave_bits |= bit
                    if grid[gy][gx]:
                        grid_bits |= bit
                ch = chr(0x2800 + (wave_bits | grid_bits))
                line.append(
                    ch,
                    style=(
                        wave_style if wave_bits else (grid_style if grid_bits else "")
                    ),
                )
            rows.append(line)
        return rows[:height_chars]


class WaveformView:
    def __init__(
        self, scope: WaveformScope, *, gate_open: bool, height: int = WAVEFORM_HEIGHT
    ) -> None:
        self._scope = scope
        self._gate_open = gate_open
        self._height = height

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = max(16, options.max_width)
        rows = self._scope.render_lines(
            width_chars=width, height_chars=self._height, gate_open=self._gate_open
        )
        body = Text()
        for idx, row in enumerate(rows):
            if idx:
                body.append("\n")
            body.append_text(row)
        yield from console.render(body, options)
