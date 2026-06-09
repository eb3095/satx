"""Default NOAA APT channels stored in user config."""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_APT_CHANNELS: List[Dict[str, Any]] = [
    {
        "id": "noaa-15",
        "name": "NOAA 15",
        "freq_mhz": 137.62,
        "description": "NOAA-15 APT weather downlink",
    },
    {
        "id": "noaa-18",
        "name": "NOAA 18",
        "freq_mhz": 137.9125,
        "description": "NOAA-18 APT weather downlink",
    },
    {
        "id": "noaa-19",
        "name": "NOAA 19",
        "freq_mhz": 137.1,
        "description": "NOAA-19 APT weather downlink",
    },
]
