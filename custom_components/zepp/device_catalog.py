"""Zepp / Amazfit Device Source Catalog with automatic weekly refresh."""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DEVICES_JSON_URL = (
    "https://raw.githubusercontent.com/melianmiko/ZeppOS-DevicesList/refs/heads/main/zepp_devices.json"
)
STORAGE_KEY = "zepp_devices_catalog"
STORAGE_VERSION = 1
REFRESH_INTERVAL_SECONDS = 7 * 24 * 3600  # 7 days

# Dynamic memory cache for deviceSource -> model name
_DYNAMIC_CATALOG: dict[int, str] = {
    7930112: "Amazfit GTR 4",
    7930113: "Amazfit GTR 4",
    8192257: "Amazfit Cheetah",
    8257793: "Amazfit Cheetah Square",
    8323328: "Amazfit Active",
    8323329: "Amazfit Active",
    8388864: "Amazfit Active Edge",
    8388865: "Amazfit Active Edge",
    8454400: "Amazfit Bip 5",
    8454401: "Amazfit Bip 5",
    8519936: "Amazfit Balance",
    8519937: "Amazfit Balance",
    8519939: "Amazfit Balance",
    6553856: "Amazfit T-Rex Ultra",
    6553857: "Amazfit T-Rex Ultra",
    8716544: "Amazfit T-Rex 3",
    8716545: "Amazfit T-Rex 3",
    8716547: "Amazfit T-Rex 3",
    8782081: "Amazfit Bip 5 Unity",
    8913155: "Amazfit Active 2",
    9568512: "Amazfit Balance 2",
    9765120: "Amazfit Bip 6",
    10158337: "Amazfit Bip 6",
    10879233: "Amazfit T-Rex Ultra 2",
    11141377: "Amazfit Balance 3",
}


def _update_memory_catalog(items: list[dict[str, Any]]) -> None:
    """Parse list of device dicts into memory mapping."""
    for dev in items:
        name = dev.get("deviceName", "")
        if dev.get("alternativeDeviceNames"):
            name = dev["alternativeDeviceNames"][0]
        elif not name.startswith("Amazfit") and not name.startswith("Mi "):
            name = f"Amazfit {name}"

        sources = dev.get("deviceSource", [])
        if isinstance(sources, list):
            for src in sources:
                if isinstance(src, int):
                    _DYNAMIC_CATALOG[src] = name


async def async_init_device_catalog(hass: HomeAssistant) -> None:
    """Load cached devices catalog from storage or fetch fresh version every 7 days."""
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    cached = await store.async_load()

    now = time.time()
    need_fetch = True

    if cached and isinstance(cached, dict):
        last_updated = cached.get("last_updated", 0)
        items = cached.get("items", [])
        if items:
            _update_memory_catalog(items)
        if now - last_updated < REFRESH_INTERVAL_SECONDS:
            need_fetch = False

    if need_fetch:
        hass.async_create_task(_async_fetch_remote_catalog(hass, store))


async def _async_fetch_remote_catalog(hass: HomeAssistant, store: Store[dict[str, Any]]) -> None:
    """Download latest devices json and persist to HA storage."""
    try:
        session = async_get_clientsession(hass)
        async with session.get(DEVICES_JSON_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if isinstance(data, list):
                    _update_memory_catalog(data)
                    await store.async_save({
                        "last_updated": time.time(),
                        "items": data,
                    })
                    _LOGGER.debug("Successfully updated Zepp devices catalog from remote repository (%d devices)", len(data))
    except Exception as err:
        _LOGGER.debug("Could not refresh Zepp devices catalog from remote: %s", err)


def resolve_device_name(device_source: int | None, display_name: str | None = None) -> str:
    """Resolve friendly device name from deviceSource code or user display name."""
    if display_name and display_name.strip():
        return display_name.strip()
    if device_source and device_source in _DYNAMIC_CATALOG:
        return _DYNAMIC_CATALOG[device_source]
    return "Amazfit Watch"

