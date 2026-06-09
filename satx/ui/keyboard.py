"""Non-blocking terminal key polling for live UI controls."""

from __future__ import annotations

import atexit
import os
import select
import sys
import termios
import time
import tty
from contextlib import contextmanager
from typing import Iterator, Optional

_pending = ""
_ESC_WAIT_SEC = 0.12
_saved_termios: Optional[list[int]] = None


def restore_terminal() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25h\x1b[?1049l\x1b[0m")
        sys.stdout.flush()
    if _saved_termios is not None and sys.stdin.isatty():
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _saved_termios)
        except termios.error:
            pass


atexit.register(restore_terminal)


@contextmanager
def terminal_session() -> Iterator[None]:
    global _saved_termios
    if not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    _saved_termios = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[tty.LFLAG] &= ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    try:
        yield
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, _saved_termios)
        except termios.error:
            pass
        _saved_termios = None
        restore_terminal()


def _read_available() -> str:
    chunks: list[bytes] = []
    fd = sys.stdin.fileno()
    while select.select([sys.stdin], [], [], 0)[0]:
        part = os.read(fd, 64)
        if not part:
            break
        chunks.append(part)
    return b"".join(chunks).decode("utf-8", errors="replace") if chunks else ""


def _esc_sequence_complete(raw: str) -> bool:
    if not raw.startswith("\x1b") or len(raw) < 2:
        return False
    rest = raw[1:]
    return rest[0] in "[O" and rest[-1].isalpha()


def _wait_for_esc_completion(prefix: str) -> str:
    buf = prefix
    deadline = time.monotonic() + _ESC_WAIT_SEC
    fd = sys.stdin.fileno()
    while time.monotonic() < deadline and not _esc_sequence_complete(buf):
        remaining = deadline - time.monotonic()
        ready, _, _ = select.select([sys.stdin], [], [], min(remaining, 0.02))
        if not ready:
            continue
        part = os.read(fd, 64)
        if not part:
            break
        buf += part.decode("utf-8", errors="replace")
    return buf


def _take_first_key(data: str) -> tuple[str, str]:
    if not data:
        return "", ""
    if data[0] != "\x1b":
        return data[0], data[1:]
    if len(data) == 1:
        return data, ""
    rest = data[1:]
    if rest[0] not in "[O":
        return "\x1b", data[1:]
    for idx in range(2, len(rest) + 1):
        candidate = "\x1b" + rest[:idx]
        if _esc_sequence_complete(candidate):
            return candidate, data[len(candidate) :]
    return data, ""


def _read_key_bytes() -> str:
    global _pending
    data = _pending + _read_available()
    _pending = ""
    key, remainder = _take_first_key(data)
    if not key:
        return ""
    if key.startswith("\x1b") and not _esc_sequence_complete(key):
        key = _wait_for_esc_completion(key)
        if not _esc_sequence_complete(key):
            _pending = key + remainder
            return ""
    _pending = remainder
    return key


def _decode_key(raw: str) -> Optional[str]:
    if raw in ("\x03", "\x04"):
        return "quit"
    if raw in ("[", "?"):
        return "prev"
    if raw in ("]", "/"):
        return "next"
    if raw in ("g",):
        return "first"
    if raw in ("G",):
        return "last"
    if raw in ("a", "A"):
        return "dashboard_apt"
    if raw in ("l", "L"):
        return "dashboard_lrpt"
    if raw in ("i", "I"):
        return "dashboard_ism"
    if raw in ("r", "R"):
        return "dashboard_sat_radio"
    if raw in ("s", "S"):
        return "save_image"
    if raw in ("+", "="):
        return "volume_up"
    if raw == "-":
        return "volume_down"
    if not raw.startswith("\x1b"):
        return None
    rest = raw[1:]
    if not rest:
        return None
    if rest[0] in "[O":
        final = rest[-1]
        if final == "D":
            return "prev"
        if final == "C":
            return "next"
        if final == "A":
            return "channel_up"
        if final == "B":
            return "channel_down"
        if final == "H":
            return "first"
        if final == "F":
            return "last"
    return None


def poll_key() -> Optional[str]:
    if not sys.stdin.isatty():
        return None
    if not _pending and not select.select([sys.stdin], [], [], 0)[0]:
        return None
    raw = _read_key_bytes()
    return _decode_key(raw) if raw else None


def drain_keys() -> list[str]:
    keys: list[str] = []
    while True:
        key = poll_key()
        if key is None:
            break
        keys.append(key)
    return keys


def reset_pending() -> None:
    global _pending
    _pending = ""
