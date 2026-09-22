"""The Zepp (Amazfit) integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import ZeppCoordinator
from .device_catalog import async_init_device_catalog
from .history_sync import async_sync_historical_data
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Zepp component."""
    await async_register_services(hass)
    await async_init_device_catalog(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zepp from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await async_init_device_catalog(hass)

    coordinator = ZeppCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Launch background historical backfill (initial 365 days / 1 year)
    sync_task = hass.async_create_task(
        async_sync_historical_data(hass, entry.data, days=365)
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "data": entry.data,
        "coordinator": coordinator,
        "history_sync_task": sync_task,
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_info = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_info:
        sync_task = entry_info.get("history_sync_task")
        if sync_task and not sync_task.done():
            _LOGGER.debug("Cancelling active historical sync task during unload")
            sync_task.cancel()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
