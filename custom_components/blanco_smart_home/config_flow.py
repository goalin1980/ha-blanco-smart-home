"""Config flow for BLANCO Smart Home Cloud."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoAuthError,
    BlancoConnectionError,
    BlancoDeviceTypeError,
    BlancoInvalidTokenError,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, __version__
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_SERVICE_CODE,
    CONF_TOKEN_TYPE,
    DOMAIN,
    INTEGRATION_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(suggested: dict[str, Any] | None = None) -> vol.Schema:
    """Return a schema that masks the service code in the browser."""
    suggested = suggested or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SERIAL, default=suggested.get(CONF_SERIAL, vol.UNDEFINED)
            ): TextSelector(TextSelectorConfig()),
            vol.Required(CONF_SERVICE_CODE): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


def _error_key(error: Exception) -> str:
    """Map API exceptions to translated config-flow errors."""
    if isinstance(error, BlancoAuthError):
        return "access_not_granted"
    if isinstance(error, BlancoDeviceTypeError):
        return "device_type_not_supported"
    if isinstance(error, BlancoInvalidTokenError):
        return "invalid_auth"
    if isinstance(error, BlancoConnectionError):
        return "cannot_connect"
    return "unknown"


class BlancoSmartHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration and reauthentication."""

    VERSION = 1
    _pending_client: BlancoApiClient | None = None
    _pending_app_id: str | None = None

    async def _async_register_and_authenticate(self, dev_id: str) -> dict[str, Any]:
        """Register once per flow and authenticate one BLANCO device."""
        locale = self.hass.config.language.split("-")[0][:2]
        if self._pending_client is None:
            self._pending_client = BlancoApiClient(
                async_get_clientsession(self.hass),
                app_version=INTEGRATION_VERSION,
                app_build="1",
                os_version=__version__,
            )
        if self._pending_app_id is None:
            registration = await self._pending_client.register_app(locale)
            self._pending_app_id = registration["app_id"]

        authentication = await self._pending_client.authenticate(dev_id)
        return {
            CONF_APP_ID: self._pending_app_id,
            CONF_APP_LOCALE: locale,
            CONF_TOKEN: authentication["token"],
            CONF_TOKEN_TYPE: authentication["token_type"],
            CONF_DEV_TYPE: authentication["dev_type"],
            CONF_DEV_ID: dev_id,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a device with its serial number and Smart Home service code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            serial = str(user_input[CONF_SERIAL]).strip()
            service_code = str(user_input[CONF_SERVICE_CODE]).strip()
            if not serial or not service_code:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                dev_id = BlancoApiClient.compute_dev_id(serial, service_code)
                try:
                    auth_data = await self._async_register_and_authenticate(dev_id)
                except (
                    BlancoAuthError,
                    BlancoConnectionError,
                    BlancoDeviceTypeError,
                    BlancoInvalidTokenError,
                ) as err:
                    errors["base"] = _error_key(err)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.exception(
                        "Unexpected error while configuring BLANCO Smart Home"
                    )
                    errors["base"] = _error_key(err)
                else:
                    return self.async_create_entry(
                        title=f"BLANCO {serial[-4:]}",
                        data={CONF_SERIAL: serial, **auth_data},
                    )

        suggested = (
            {CONF_SERIAL: user_input.get(CONF_SERIAL, "")}
            if user_input is not None
            else None
        )
        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(suggested),
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication after cloud access has been revoked."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create fresh app credentials after RCA was activated again."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                auth_data = await self._async_register_and_authenticate(
                    str(entry.data[CONF_DEV_ID])
                )
            except (
                BlancoAuthError,
                BlancoConnectionError,
                BlancoDeviceTypeError,
                BlancoInvalidTokenError,
            ) as err:
                errors["base"] = _error_key(err)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception(
                    "Unexpected error while reauthenticating BLANCO Smart Home"
                )
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={**entry.data, **auth_data},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )
