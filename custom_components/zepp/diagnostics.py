"""Diagnostics support for Zepp (Amazfit) integration."""
from __future__ import annotations

from collections import deque
import datetime
import logging
import re
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


class ZeppLogCaptureHandler(logging.Handler):
    """In-memory ring buffer capturing recent component log records."""

    def __init__(self, maxlen: int = 100) -> None:
        super().__init__()
        self.records: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Redact sensitive credentials and hardware identifiers from log messages
            msg = re.sub(r"UQVB[a-zA-Z0-9_\-]{30,}", "[REDACTED_APPTOKEN]", msg)
            msg = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]", msg)
            msg = re.sub(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", "[REDACTED_MAC]", msg)

            d = datetime.datetime.fromtimestamp(record.created)
            self.records.append({
                "timestamp": d.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
            })
        except Exception:
            pass


_LOG_CAPTURE = ZeppLogCaptureHandler(maxlen=100)
_LOG_CAPTURE.setFormatter(logging.Formatter("%(message)s"))
_LOG_CAPTURE.setLevel(logging.DEBUG)

# Attach capture handler to root integration logger
_zepp_logger = logging.getLogger("custom_components.zepp")
if _LOG_CAPTURE not in _zepp_logger.handlers:
    _zepp_logger.addHandler(_LOG_CAPTURE)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return comprehensive diagnostics for a config entry with redacted secrets and recent logs."""
    entry_dict = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator: ZeppCoordinator | None = entry_dict.get("coordinator")

    coordinator_data = dict(coordinator.data) if coordinator and coordinator.data else {}

    # Build sensor availability summary
    metrics_summary = {}
    for metric_name, val in coordinator_data.items():
        if metric_name in ("device_batteries", "last_updated"):
            continue
        metrics_summary[metric_name] = {
            "available": val is not None,
            "sample_value": val if isinstance(val, (int, float, str, bool)) else type(val).__name__,
        }

    return {
        "system_status": {
            "version": entry.version,
            "entry_id": entry.entry_id,
            "region_host": entry.data.get("region_host"),
            "scan_interval": str(coordinator.update_interval) if coordinator else "unknown",
            "last_update_success": coordinator.last_update_success if coordinator else False,
            "last_updated": coordinator_data.get("last_updated"),
            "devices_count": len(entry.data.get("devices", [])),
            "options": dict(entry.options),
        },
        "devices": [
            async_redact_data(dict(dev), TO_REDACT)
            for dev in entry.data.get("devices", [])
        ],
        "metrics_health": metrics_summary,
        "raw_coordinator_data": async_redact_data(coordinator_data, TO_REDACT),
        "recent_logs": list(_LOG_CAPTURE.records),
    }
