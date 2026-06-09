"""Compact braille previews for the Rich terminal UI."""

from __future__ import annotations

from typing import List

import numpy as np
from rich.text import Text


def braille_lines(image: np.ndarray, rows: int = 8) -> List[Text]:
    if image.ndim != 2 or image.size == 0 or rows <= 0:
        return []
    height, width = image.shape
    lines: List[Text] = []
    for row_idx in range(rows):
        y = int(row_idx * height / rows)
        row = image[y]
        step = max(1, width // 80)
        chars: list[str] = []
        for pixel in row[::step]:
            if pixel < 64:
                chars.append(" ")
            elif pixel < 128:
                chars.append("░")
            elif pixel < 192:
                chars.append("▒")
            else:
                chars.append("█")
        lines.append(Text("".join(chars), style="dim"))
    return lines
