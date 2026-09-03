"""BLANCO Smart Home Cloud integration."""

from __future__ import annotations

import contextlib

from blanco_smart_home_api_client import BlancoApiClient, BlancoApiError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform, __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_APP_ID,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_TOKEN_TYPE,
    INTEGRATION_VERSION,
)
from .coordinator import BlancoDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

BlancoConfigEntry = ConfigEntry[BlancoDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Set up a BLANCO device from a config entry."""
    coordinator = BlancoDataUpdateCoordinator(
        hass,
        entry,
        token=str(entry.data[CONF_TOKEN]),
        token_type=str(entry.data.get(CONF_TOKEN_TYPE, "Bearer")),
        dev_id=str(entry.data[CONF_DEV_ID]),
        dev_type=entry.data.get(CONF_DEV_TYPE),
        serial=str(entry.data[CONF_SERIAL]),
        app_id=str(entry.data[CONF_APP_ID]),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Unload a BLANCO config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> None:
    """Deregister this integration instance from BLANCO when it is removed."""
    app_id = entry.data.get(CONF_APP_ID)
    token = entry.data.get(CONF_TOKEN)
    if not app_id or not token:
        return

    client = BlancoApiClient(
        async_get_clientsession(hass),
        app_id=str(app_id),
        token=str(token),
        token_type=str(entry.data.get(CONF_TOKEN_TYPE, "Bearer")),
        dev_id=str(entry.data.get(CONF_DEV_ID, "")),
        app_version=INTEGRATION_VERSION,
        app_build="1",
        os_version=__version__,
    )
    with contextlib.suppress(BlancoApiError):
        await client.deregister_app()
