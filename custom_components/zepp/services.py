"""Services for Zepp (Amazfit) integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .history_sync import async_sync_historical_data

_LOGGER = logging.getLogger(__name__)

SERVICE_SYNC_HISTORY = "sync_history"


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Zepp integration services."""

    async def handle_sync_history(call: ServiceCall) -> None:
        """Handle sync_history service call."""
        days = call.data.get("days", 365)
        entries = hass.data.get(DOMAIN, {})

        for entry_id, entry_info in entries.items():
            if isinstance(entry_info, dict) and "data" in entry_info:
                entry_data = entry_info["data"]
                _LOGGER.info("Running manual Zepp history sync for %s days", days)
                hass.async_create_task(
                    async_sync_historical_data(hass, entry_data, days=days)
                )

    if not hass.services.has_service(DOMAIN, SERVICE_SYNC_HISTORY):
        hass.services.async_register(DOMAIN, SERVICE_SYNC_HISTORY, handle_sync_history)
