from __future__ import annotations

from satx.config import RadioConfig
from satx.radio.hackrf import HackRFReceiver
from satx.radio.receiver import make_receiver
from satx.radio.rtlsdr import RtlSdrReceiver


def test_make_receiver_hackrf():
    receiver = make_receiver(RadioConfig(backend="hackrf"), freq_hz=137_100_000)
    assert isinstance(receiver, HackRFReceiver)


def test_make_receiver_rtlsdr():
    receiver = make_receiver(RadioConfig(backend="rtlsdr"), freq_hz=137_100_000)
    assert isinstance(receiver, RtlSdrReceiver)


def test_make_receiver_unknown_backend_defaults_to_hackrf():
    receiver = make_receiver(RadioConfig(backend="unknown"), freq_hz=137_100_000)  # type: ignore[arg-type]
    assert isinstance(receiver, HackRFReceiver)
