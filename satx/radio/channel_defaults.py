"""Default amateur satellite voice channels stored in user config."""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_SAT_RADIO_CHANNELS: List[Dict[str, Any]] = [
    {
        "id": "iss-voice",
        "name": "ISS Voice",
        "freq_mhz": 145.8,
        "description": "International Space Station FM voice downlink",
    },
    {
        "id": "iss-aprs",
        "name": "ISS APRS",
        "freq_mhz": 145.825,
        "description": "ISS packet/APRS digipeater",
    },
    {
        "id": "so-50",
        "name": "SO-50",
        "freq_mhz": 436.795,
        "description": "SAUDISAT 1C FM repeater downlink",
    },
    {
        "id": "ao-91",
        "name": "AO-91",
        "freq_mhz": 435.25,
        "description": "Fox-1B FM repeater downlink",
    },
    {
        "id": "ao-92",
        "name": "AO-92",
        "freq_mhz": 437.715,
        "description": "Fox-1D FM repeater downlink",
    },
    {
        "id": "fo-29",
        "name": "FO-29",
        "freq_mhz": 145.95,
        "description": "Fuji-OSCAR 29 FM/CW downlink",
    },
]
