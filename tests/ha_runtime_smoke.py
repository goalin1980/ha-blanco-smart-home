"""Runtime smoke test executed inside an official Home Assistant image."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from blanco_smart_home_api_client import (
    BlancoConnectionError,
    BlancoDeviceType,
    BlancoErrorType,
    BlancoWaterType,
    HttpStatus,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from custom_components.blanco_smart_home.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    BlancoBinarySensor,
)
from custom_components.blanco_smart_home.const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_TOKEN_TYPE,
    DATA_HISTORY,
)
from custom_components.blanco_smart_home.coordinator import (
    BlancoDataUpdateCoordinator,
)
from custom_components.blanco_smart_home.sensor import (
    SENSOR_DESCRIPTIONS,
    BlancoSensor,
)


async def main() -> None:
    """Exercise a complete coordinator refresh with mocked cloud responses."""
    hass = HomeAssistant("/tmp/blanco-ha-runtime")
    entry = MagicMock()
    entry.data = {
        CONF_APP_ID: "test-app",
        CONF_APP_LOCALE: "en",
        CONF_DEV_ID: "test-device-id",
        CONF_DEV_TYPE: int(BlancoDeviceType.AIO),
        CONF_SERIAL: "001234",
        CONF_TOKEN_TYPE: "Bearer",
        CONF_TOKEN: "test-token",
    }
    entry.async_on_unload = MagicMock()

    with patch(
        "custom_components.blanco_smart_home.coordinator.async_get_clientsession",
        return_value=MagicMock(),
    ):
        coordinator = BlancoDataUpdateCoordinator(
            hass,
            entry,
            token="test-token",
            token_type="Bearer",
            dev_id="test-device-id",
            dev_type=int(BlancoDeviceType.AIO),
            serial="001234",
            app_id="test-app",
        )

    api = MagicMock()
    api.get_device_system = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {
                "params": {"dev_name": "Kitchen", "sw_ver_main_con": "1.2.3"},
                "info": {"connected": True, "online": 1_788_000_000_000},
            },
        )
    )
    api.get_device_status = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {"params": {"filter_rest": 80, "co2_rest": 70}, "info": {}},
        )
    )
    api.get_device_settings = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {
                "params": {
                    "set_point_cooling": 6,
                    "set_point_heating": 95,
                    "absence_mode_active": False,
                    "child_protect": True,
                },
                "info": {},
            },
        )
    )
    api.get_device_errors = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {
                "errors": [
                    {
                        "err_code": 42,
                        "err_type": BlancoErrorType.WARNING,
                        "err_ts": 1_788_000_000_000,
                    }
                ],
                "info": {},
            },
        )
    )
    api.get_device_actions = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {
                "actions": [
                    {
                        "evt_ts": 1_788_000_000_000,
                        "disp_wtr_amt": 250,
                        "tap_state": BlancoWaterType.STILL,
                    }
                ],
                "info": {},
            },
        )
    )
    api.get_device_stats = AsyncMock(
        return_value=(
            HttpStatus.OK,
            {
                "ranges": [
                    {
                        "range": {"lod": lod},
                        "total": [{"par": "disp_wtr_amt", "val": lod * 1000}],
                        "details": [],
                    }
                    for lod in (4, 1, 3, 2)
                ],
                "info": {},
            },
        )
    )
    coordinator._api = api

    data = await coordinator._async_update_data()
    coordinator.data = data
    assert data[DATA_HISTORY]["last_dispense_ml"] == 250
    assert data[DATA_HISTORY]["last_water_type"] == "still"
    assert data[DATA_HISTORY]["water_today_l"] == 1.0
    assert data[DATA_HISTORY]["water_year_l"] == 4.0
    assert coordinator.endpoint_available("stats")

    sensor_descriptions = {item.key: item for item in SENSOR_DESCRIPTIONS}
    filter_sensor = BlancoSensor(coordinator, sensor_descriptions["filter_rest"])
    warning_sensor = BlancoSensor(
        coordinator, sensor_descriptions["error_count_warning"]
    )
    assert filter_sensor.available
    assert filter_sensor.native_value == 80
    assert warning_sensor.native_value == 1
    assert filter_sensor.device_info["manufacturer"] == "BLANCO"

    binary_descriptions = {item.key: item for item in BINARY_SENSOR_DESCRIPTIONS}
    problem_sensor = BlancoBinarySensor(coordinator, binary_descriptions["has_problem"])
    hot_water_sensor = BlancoBinarySensor(
        coordinator, binary_descriptions["hot_water_enabled"]
    )
    assert problem_sensor.is_on
    assert hot_water_sensor.is_on is False

    api.get_device_errors.side_effect = BlancoConnectionError("temporary outage")
    stale_data = await coordinator._async_update_data()
    coordinator.data = stale_data
    assert warning_sensor.native_value == 1
    assert not warning_sensor.available
    assert filter_sensor.available
    print("Coordinator refresh passed in Home Assistant runtime")


if __name__ == "__main__":
    asyncio.run(main())
