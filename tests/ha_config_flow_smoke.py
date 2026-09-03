"""Config-flow smoke test executed inside an official Home Assistant image."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.blanco_smart_home.const import CONF_SERVICE_CODE, DOMAIN


async def main() -> None:
    """Run the real HA flow manager with a mocked BLANCO client."""
    hass = HomeAssistant("/config")
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()

    with (
        patch(
            "custom_components.blanco_smart_home.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.blanco_smart_home.config_flow.BlancoApiClient"
        ) as client_class,
        patch(
            "custom_components.blanco_smart_home.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        client_class.compute_dev_id.return_value = "hashed-device-id"
        client = client_class.return_value
        client.register_app = AsyncMock(return_value={"app_id": "test-app"})
        client.authenticate = AsyncMock(
            return_value={"token": "test-token", "token_type": "Bearer", "dev_type": 2}
        )

        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert form["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {"serial": "001234", "service_code": "one-time-secret"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["serial"] == "001234"
        assert CONF_SERVICE_CODE not in result["data"]
        assert result["data"]["app_id"] == "test-app"

        second_form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        duplicate = await hass.config_entries.flow.async_configure(
            second_form["flow_id"],
            {"serial": "001234", "service_code": "one-time-secret"},
        )
        assert duplicate["type"] is FlowResultType.ABORT
        assert duplicate["reason"] == "already_configured"

        entry = result["result"]
        reauth_form = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=dict(entry.data),
        )
        assert reauth_form["type"] is FlowResultType.FORM
        assert reauth_form["step_id"] == "reauth_confirm"
        reauth_result = await hass.config_entries.flow.async_configure(
            reauth_form["flow_id"], {}
        )
        assert reauth_result["type"] is FlowResultType.ABORT
        assert reauth_result["reason"] == "reauth_successful"

    print("Config flow passed in Home Assistant runtime")


if __name__ == "__main__":
    asyncio.run(main())
