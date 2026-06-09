"""Append-only session logs under ~/.satx/logs/."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import TextIO


def default_log_dir() -> Path:
    override = os.environ.get("SATX_LOG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".satx" / "logs"


def default_image_dir() -> Path:
    override = os.environ.get("SATX_IMAGE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".satx" / "images"


def _safe_path_part(value: str) -> str:
    cleaned = value.strip().replace("/", "-").replace(" ", "-")
    return cleaned or "unknown"


def image_save_path(
    image_dir: Path,
    image_type: str,
    channel: str,
    *,
    when: float | None = None,
) -> Path:
    """Build ~/.satx/images/{type}_{channel}_{timestamp}.png"""
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(when or time.time()))
    name = f"{_safe_path_part(image_type)}_{_safe_path_part(channel)}_{stamp}.png"
    return image_dir / name


def mhz_log_name(prefix: str, freq_mhz: float) -> str:
    return f"{prefix}_{freq_mhz:.3f}"


class LogWriter:
    def __init__(self, log_dir: Path | None = None) -> None:
        self._dir = log_dir or default_log_dir()
        self._files: dict[str, TextIO] = {}
        self._lock = threading.Lock()

    @property
    def log_dir(self) -> Path:
        return self._dir

    def _append(self, stem: str, line: str) -> None:
        text = line.replace("\n", " ").replace("\r", " ").strip()
        if not text:
            return
        with self._lock:
            handle = self._files.get(stem)
            if handle is None:
                self._dir.mkdir(parents=True, exist_ok=True)
                path = self._dir / f"{stem}.log"
                handle = open(path, "a", encoding="utf-8", buffering=1)
                self._files[stem] = handle
            handle.write(text + "\n")
            handle.flush()

    def log_apt(self, line: str) -> None:
        self._append("apt", line)

    def log_lrpt(self, line: str) -> None:
        self._append("lrpt", line)

    def log_ism(self, line: str) -> None:
        self._append("ism", line)

    def log_radio_transcript(self, freq_mhz: float, text: str) -> None:
        self._append(mhz_log_name("radio", freq_mhz), text)

    def close(self) -> None:
        with self._lock:
            for handle in self._files.values():
                handle.close()
            self._files.clear()
