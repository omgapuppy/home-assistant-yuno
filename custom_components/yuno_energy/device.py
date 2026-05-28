"""Device metadata helpers for Yuno Energy."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN


def device_info_for_entry(entry_id: str) -> Any:
    """Return Home Assistant device metadata for a Yuno config entry."""
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "manufacturer": "Yuno Energy Ireland",
        "model": "Electricity usage",
        "name": "Yuno Energy",
    }
