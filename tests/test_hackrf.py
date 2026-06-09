from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from satx.config import RadioConfig
from satx.radio import hackrf as hackrf_module
from satx.radio.hackrf import HackRFReceiver, _failure_line


def test_failure_line_prefers_error():
    text = "call hackrf_set_sample_rate(2000000 Hz/2.000 MHz)\nhackrf_open() failed: HackRF not found (-5)"
    assert "HackRF not found" in _failure_line(text)


def test_check_device_raises_when_info_fails():
    with patch.object(
        HackRFReceiver, "find_binary", return_value="/usr/bin/hackrf_transfer"
    ):
        with patch.object(
            HackRFReceiver,
            "find_info_binary",
            return_value="/usr/bin/hackrf_info",
        ):
            with patch(
                "satx.radio.hackrf.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["hackrf_info"],
                    returncode=1,
                    stdout=b"",
                    stderr=b"hackrf_open() failed: HackRF not found (-5)\n",
                ),
            ):
                with pytest.raises(RuntimeError, match="HackRF not found"):
                    HackRFReceiver.check_device()


def test_start_raises_when_process_exits_immediately():
    receiver = HackRFReceiver(RadioConfig(), freq_hz=137_100_000)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1

    with patch.object(HackRFReceiver, "check_device"):
        with patch.object(
            HackRFReceiver, "find_binary", return_value="/usr/bin/hackrf_transfer"
        ):
            with patch("satx.radio.hackrf.subprocess.Popen", return_value=mock_proc):
                with patch.object(
                    receiver,
                    "_probe_start_failure",
                    return_value="hackrf_open() failed: HackRF not found (-5)",
                ):
                    with pytest.raises(RuntimeError, match="HackRF not found"):
                        receiver.start()


def test_running_false_after_exit():
    receiver = HackRFReceiver(RadioConfig(), freq_hz=137_100_000)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    receiver._proc = mock_proc
    assert receiver.exited is True
    assert receiver.running is False


def test_live_capture_uses_devnull_stderr():
    source = open(hackrf_module.__file__, encoding="utf-8").read()
    assert "stderr=subprocess.DEVNULL" in source
