"""Button platform for Zepp (Amazfit) integration."""
from __future__ import annotations

import logging
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_USERID, DOMAIN
from .coordinator import ZeppCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zepp buttons."""
    coordinator: ZeppCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entry_data = entry.data
    userid = str(entry_data[CONF_USERID])
    devices = entry_data.get("devices", [])

    if not devices:
        devices = [{
            "device_id": userid,
            "device_name": "Amazfit Watch",
            "device_mac": "",
            "device_sn": "",
            "firmware": "",
        }]

    buttons: list[ButtonEntity] = []
    for dev in devices:
        device_id = str(dev.get("device_id", userid))
        device_name = str(dev.get("device_name", "Amazfit Watch"))
        mac = str(dev.get("device_mac", ""))
        sn = str(dev.get("device_sn", ""))
        fw = str(dev.get("firmware", ""))

        connections = set()
        if mac and mac != "Unknown":
            connections.add((dr.CONNECTION_NETWORK_MAC, mac))

        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Amazfit",
            model=device_name,
            sw_version=fw or None,
            serial_number=sn or None,
            connections=connections,
        )

        buttons.append(ZeppSyncButton(coordinator, device_id, device_name, device_info))

    async_add_entities(buttons)


class ZeppSyncButton(ButtonEntity):
    """Button to trigger an immediate Zepp cloud sync."""

    _attr_has_entity_name = True
    _attr_name = "Sync Now"
    _attr_icon = "mdi:sync"
    _attr_device_class = ButtonDeviceClass.UPDATE

    def __init__(
        self,
        coordinator: ZeppCoordinator,
        device_id: str,
        device_name: str,
        device_info: DeviceInfo,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{device_id}_sync_now"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Handle the button press: request an immediate coordinator refresh."""
        _LOGGER.debug("ZeppSyncButton pressed, requesting coordinator refresh")
        await self._coordinator.async_request_refresh()
