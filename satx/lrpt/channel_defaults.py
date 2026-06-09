"""Default METEOR LRPT channels stored in user config."""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_LRPT_CHANNELS: List[Dict[str, Any]] = [
    {
        "id": "meteor-m2",
        "name": "METEOR M2",
        "freq_mhz": 137.9,
        "description": "METEOR-M2 LRPT downlink",
    },
    {
        "id": "meteor-m2-2",
        "name": "METEOR M2-2",
        "freq_mhz": 137.9,
        "description": "METEOR-M2-2 LRPT downlink",
    },
]
