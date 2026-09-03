"""Diagnostics for BLANCO Smart Home Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BlancoConfigEntry
from .const import (
    CONF_APP_ID,
    CONF_DEV_ID,
    CONF_SERIAL,
    CONF_SERVICE_CODE,
)

_REDACT = {
    "api_key",
    "app_id",
    "authorization",
    "bssid",
    "dev_id",
    "device_id",
    "ip",
    "mac",
    "pairing_code",
    "password",
    "serial",
    "service_code",
    "ssid",
    "token",
    "wifi_password",
    CONF_APP_ID,
    CONF_DEV_ID,
    CONF_SERIAL,
    CONF_SERVICE_CODE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BlancoConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot suitable for mapping new device fields."""
    return {
        "config_entry": async_redact_data(dict(entry.data), _REDACT),
        "device_type": (
            entry.runtime_data.dev_type.name
            if entry.runtime_data.dev_type is not None
            else None
        ),
        "coordinator": async_redact_data(dict(entry.runtime_data.data or {}), _REDACT),
    }
