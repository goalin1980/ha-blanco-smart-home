"""Update coordinator for BLANCO Smart Home Cloud."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoApiError,
    BlancoConnectionError,
    BlancoDeviceType,
    HttpStatus,
)
from homeassistant.const import CONF_TOKEN, EVENT_CORE_CONFIG_UPDATE, __version__
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_APP_LOCALE,
    CONF_TOKEN_TYPE,
    DATA_ACTIONS,
    DATA_API_STATUS,
    DATA_AVAILABLE,
    DATA_ERRORS,
    DATA_HISTORY,
    DATA_SETTINGS,
    DATA_STATUS,
    DATA_SYSTEM,
    DOMAIN,
    HISTORY_UPDATE_INTERVAL,
    INTEGRATION_VERSION,
    UPDATE_INTERVAL,
)
from .helpers import (
    compute_stats_ranges,
    extract_period_totals,
    summarize_latest_dispense,
)

_LOGGER = logging.getLogger(__name__)

_HISTORY_DEVICE_PARAMETER: dict[BlancoDeviceType, str] = {
    BlancoDeviceType.SODA: "disp_wtr_amt",
    BlancoDeviceType.AIO: "disp_wtr_amt",
    BlancoDeviceType.AQUA: "wtr_flow",
}
_RECENT_ACTION_WINDOW = timedelta(days=30)

_EMPTY_EVENT: dict[str, dict[str, Any]] = {"params": {}, "info": {}}
_EMPTY_ERRORS: dict[str, Any] = {"errors": [], "info": {}}
_EMPTY_ACTIONS: dict[str, Any] = {"actions": [], "info": {}}
_EMPTY_HISTORY: dict[str, Any] = {
    "last_dispense_ml": None,
    "last_dispense_ts": None,
    "last_water_type": None,
    "water_today_l": None,
    "water_week_l": None,
    "water_month_l": None,
    "water_year_l": None,
}

ApiMethod = Callable[[str], Awaitable[tuple[int, Any]]]


class BlancoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the read-only BLANCO Smart Home API endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: Any,
        *,
        token: str,
        token_type: str,
        dev_id: str,
        dev_type: int | None,
        serial: str,
        app_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.dev_id = dev_id
        self.serial = serial
        try:
            self.dev_type = BlancoDeviceType(dev_type) if dev_type is not None else None
        except ValueError:
            self.dev_type = None

        self._next_history_update = 0.0
        self._unsupported_endpoints: set[str] = set()
        self._api = BlancoApiClient(
            async_get_clientsession(hass),
            app_id=app_id,
            token=token,
            token_type=token_type,
            dev_id=dev_id,
            app_version=INTEGRATION_VERSION,
            app_build="1",
            os_version=__version__,
            on_token_renewed=self._persist_renewed_token,
        )
        self._setup_language_listener()

    def _persist_renewed_token(self, token: str, token_type: str) -> None:
        """Persist credentials renewed transparently by the API client."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: token,
                CONF_TOKEN_TYPE: token_type,
            },
        )

    def _setup_language_listener(self) -> None:
        """Keep the API app locale synchronized with Home Assistant."""

        async def _handle_language_change(event: Event) -> None:
            if "language" not in event.data:
                return
            locale = self.hass.config.language.split("-")[0][:2]
            if locale == self.config_entry.data.get(CONF_APP_LOCALE):
                return
            try:
                updated = await self._api.update_app_locale(locale)
            except BlancoConnectionError:
                return
            if updated:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_APP_LOCALE: locale},
                )

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, _handle_language_change
            )
        )

    async def _fetch_endpoint(
        self,
        name: str,
        method: ApiMethod,
        previous: dict[str, Any],
        default: dict[str, Any],
    ) -> tuple[dict[str, Any], bool, int | str]:
        """Fetch one endpoint while retaining its prior value on failure."""
        if name in self._unsupported_endpoints:
            return previous.get(name, default), False, int(HttpStatus.NOT_FOUND)
        try:
            status, result = await method(self.dev_id)
        except BlancoConnectionError as err:
            _LOGGER.warning("BLANCO %s endpoint unavailable: %s", name, err)
            return previous.get(name, default), False, "connection_error"
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err

        if status == HttpStatus.OK:
            normalized = dict(result)
            if name == DATA_ERRORS:
                normalized["errors"] = normalized.get("errors") or []
            else:
                normalized["params"] = normalized.get("params") or {}
            normalized["info"] = normalized.get("info") or {}
            return normalized, True, int(status)

        if status == HttpStatus.FORBIDDEN:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            )

        if status == HttpStatus.NOT_FOUND:
            self._unsupported_endpoints.add(name)

        _LOGGER.warning(
            "BLANCO %s endpoint returned HTTP %s; retaining previous data",
            name,
            status,
        )
        return previous.get(name, default), False, int(status)

    async def _fetch_history(
        self, previous: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | str], dict[str, bool]]:
        """Refresh lower-frequency dispense actions and aggregate statistics."""
        history = {**_EMPTY_HISTORY, **previous.get(DATA_HISTORY, {})}
        actions = previous.get(DATA_ACTIONS, _EMPTY_ACTIONS)
        endpoint_status: dict[str, int | str] = {}
        available: dict[str, bool] = {}

        if self.dev_type not in _HISTORY_DEVICE_PARAMETER:
            return history, actions, endpoint_status, available

        now_utc = datetime.now(tz=UTC)
        recent_from = int((now_utc - _RECENT_ACTION_WINDOW).timestamp() * 1000)
        try:
            status, result = await self._api.get_device_actions(
                self.dev_id, from_ts=recent_from, count=50, asc=False
            )
        except BlancoConnectionError as err:
            _LOGGER.warning("BLANCO actions endpoint unavailable: %s", err)
            endpoint_status[DATA_ACTIONS] = "connection_error"
            available[DATA_ACTIONS] = False
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        else:
            endpoint_status[DATA_ACTIONS] = int(status)
            if status == HttpStatus.OK:
                actions = dict(result)
                actions["actions"] = actions.get("actions") or []
                actions["info"] = actions.get("info") or {}
                history.update(summarize_latest_dispense(actions.get("actions", [])))
                available[DATA_ACTIONS] = True
            elif status == HttpStatus.FORBIDDEN:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                )
            else:
                available[DATA_ACTIONS] = False

        parameter = _HISTORY_DEVICE_PARAMETER[self.dev_type]
        ranges = compute_stats_ranges(now_utc, self.hass.config.time_zone)
        try:
            status, result = await self._api.get_device_stats(self.dev_id, ranges)
        except BlancoConnectionError as err:
            _LOGGER.warning("BLANCO stats endpoint unavailable: %s", err)
            endpoint_status["stats"] = "connection_error"
            available["stats"] = False
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        else:
            endpoint_status["stats"] = int(status)
            if status == HttpStatus.OK:
                totals = extract_period_totals(result.get("ranges") or [], parameter)
                history.update(
                    {f"water_{key}_l": value for key, value in totals.items()}
                )
                available["stats"] = True
            elif status == HttpStatus.FORBIDDEN:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                )
            else:
                available["stats"] = False

        return history, actions, endpoint_status, available

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all read-only device data."""
        previous: dict[str, Any] = self.data or {}
        data: dict[str, Any] = {}
        api_status: dict[str, int | str] = {}
        available: dict[str, bool] = dict(previous.get(DATA_AVAILABLE, {}))
        fresh_count = 0

        endpoints: tuple[tuple[str, ApiMethod, dict[str, Any]], ...] = (
            (DATA_SYSTEM, self._api.get_device_system, _EMPTY_EVENT),
            (DATA_STATUS, self._api.get_device_status, _EMPTY_EVENT),
            (DATA_ERRORS, self._api.get_device_errors, _EMPTY_ERRORS),
        )
        for name, method, default in endpoints:
            value, fresh, status = await self._fetch_endpoint(
                name, method, previous, default
            )
            data[name] = value
            api_status[name] = status
            available[name] = fresh
            fresh_count += int(fresh)

        if fresh_count == 0:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )

        now = time.monotonic()
        if now >= self._next_history_update:
            settings, settings_fresh, settings_status = await self._fetch_endpoint(
                DATA_SETTINGS,
                self._api.get_device_settings,
                previous,
                _EMPTY_EVENT,
            )
            data[DATA_SETTINGS] = settings
            api_status[DATA_SETTINGS] = settings_status
            available[DATA_SETTINGS] = settings_fresh

            (
                history,
                actions,
                history_status,
                history_available,
            ) = await self._fetch_history(previous)
            self._next_history_update = now + HISTORY_UPDATE_INTERVAL.total_seconds()
            api_status.update(history_status)
            available.update(history_available)
            data[DATA_HISTORY] = history
            data[DATA_ACTIONS] = actions
        else:
            data[DATA_SETTINGS] = previous.get(DATA_SETTINGS, _EMPTY_EVENT)
            data[DATA_HISTORY] = previous.get(DATA_HISTORY, _EMPTY_HISTORY)
            data[DATA_ACTIONS] = previous.get(DATA_ACTIONS, _EMPTY_ACTIONS)

        data[DATA_API_STATUS] = api_status
        data[DATA_AVAILABLE] = available
        return data

    def endpoint_available(self, endpoint: str) -> bool:
        """Return whether the most recent request for an endpoint succeeded."""
        return bool((self.data or {}).get(DATA_AVAILABLE, {}).get(endpoint, False))
