"""Live image preview without tkinter or GUI subprocesses (macOS Preview.app)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from satx.log_writer import default_image_dir

PREVIEW_MAX_WIDTH = 960
PREVIEW_MAX_HEIGHT = 720
PREVIEW_REOPEN_SEC = 1.0


def _scale_for_display(image: np.ndarray) -> Image.Image:
    img = Image.fromarray(image.astype(np.uint8), mode="L")
    width, height = img.size
    scale = min(
        PREVIEW_MAX_WIDTH / max(width, 1),
        PREVIEW_MAX_HEIGHT / max(height, 1),
        4.0,
    )
    if scale > 1.0:
        img = img.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.NEAREST,
        )
    return img


def _atomic_save_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    _scale_for_display(image).save(tmp, format="PNG")
    tmp.replace(path)


class PreviewAppImagePreview:
    """Write PNG and show in Preview.app — safe from CLI/IDE terminals on macOS."""

    def __init__(self) -> None:
        self._path = default_image_dir() / ".live_preview.png"
        self._opened = False
        self._last_open = 0.0

    @property
    def active(self) -> bool:
        return self._opened

    def start(self) -> None:
        return

    def update(self, image: np.ndarray, *, status: str = "") -> None:
        _ = status
        if image.size == 0:
            return
        _atomic_save_png(self._path, image)
        now = time.time()
        if not self._opened or now - self._last_open >= PREVIEW_REOPEN_SEC:
            subprocess.Popen(
                ["open", "-g", "-a", "Preview", str(self._path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._opened = True
            self._last_open = now

    def poll_save(self) -> bool:
        return False

    def close(self) -> None:
        if not self._opened:
            return
        self._opened = False
        path = str(self._path.resolve())
        script = (
            'tell application "Preview"\n'
            "repeat with d in documents\n"
            "try\n"
            f'if (POSIX path of d) is "{path}" then\n'
            "close d saving no\n"
            "end if\n"
            "end try\n"
            "end repeat\n"
            "end tell"
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass


class NullImagePreview:
    @property
    def active(self) -> bool:
        return False

    def start(self) -> None:
        return

    def update(self, image: np.ndarray, *, status: str = "") -> None:
        _ = image, status

    def poll_save(self) -> bool:
        return False

    def close(self) -> None:
        return


class ImagePreview:
    def __init__(self, title: str = "SatX — Live Image") -> None:
        _ = title
        if sys.platform == "darwin":
            self._backend: PreviewAppImagePreview | NullImagePreview = (
                PreviewAppImagePreview()
            )
        else:
            self._backend = NullImagePreview()

    @property
    def active(self) -> bool:
        return self._backend.active

    def start(self) -> None:
        self._backend.start()

    def update(self, image: np.ndarray, *, status: str = "") -> None:
        self._backend.update(image, status=status)

    def poll_save(self) -> bool:
        return self._backend.poll_save()

    def close(self) -> None:
        self._backend.close()


def preview_backend_name() -> str:
    if sys.platform == "darwin":
        return "preview.app"
    return "none"
