"""Yuno Energy custom integration."""

from __future__ import annotations

from typing import Any, cast

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Yuno Energy from a config entry."""
    from .coordinator import YunoEnergyCoordinator

    coordinator = YunoEnergyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload a Yuno Energy config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return cast(bool, unload_ok)
