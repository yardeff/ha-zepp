"""Diagnostics support for Zepp (Amazfit) integration."""
from __future__ import annotations

from typing import Any
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_APPTOKEN, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import ZeppCoordinator

TO_REDACT = {
    CONF_APPTOKEN,
    CONF_PASSWORD,
    CONF_EMAIL,
    "auth_key",
    "authKey",
    "device_mac",
    "macAddress",
    "bt_mac",
    "btmac",
    "sn",
    "device_sn",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry with redacted secrets."""
    coordinator: ZeppCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": async_redact_data(dict(coordinator.data), TO_REDACT),
        "devices": [
            async_redact_data(dict(dev), TO_REDACT)
            for dev in entry.data.get("devices", [])
        ],
    }
