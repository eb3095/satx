"""APT channel model and config parsing."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from satx.config import SatChannel
from satx.apt.channel_defaults import DEFAULT_APT_CHANNELS


def channel_from_dict(data: Mapping[str, Any]) -> SatChannel:
    freq_mhz = float(data["freq_mhz"])
    channel_id = str(data.get("id") or f"{freq_mhz:.3f}")
    name = str(data.get("name") or channel_id)
    description = str(data.get("description") or name)
    freq_hz = int(round(freq_mhz * 1_000_000))
    return SatChannel(
        channel_id=channel_id,
        name=name,
        freq_hz=freq_hz,
        description=description,
    )


def channel_to_dict(channel: SatChannel) -> Dict[str, Any]:
    return {
        "id": channel.channel_id,
        "name": channel.name,
        "freq_mhz": round(channel.freq_mhz, 4),
        "description": channel.description,
    }


def parse_apt_channels(
    entries: Optional[Sequence[Mapping[str, Any]]],
) -> list[SatChannel]:
    source = DEFAULT_APT_CHANNELS if not entries else entries
    return [channel_from_dict(item) for item in source]


DEFAULT_APT_CHANNEL_LIST = parse_apt_channels(None)
