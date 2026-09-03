"""Sensor entities for BLANCO Smart Home Cloud."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from blanco_smart_home_api_client import BlancoDeviceType, BlancoErrorType
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BlancoConfigEntry
from .const import (
    DATA_ACTIONS,
    DATA_ERRORS,
    DATA_HISTORY,
    DATA_SETTINGS,
    DATA_STATUS,
    DATA_SYSTEM,
)
from .coordinator import BlancoDataUpdateCoordinator
from .entity import BlancoEntity
from .helpers import timestamp_from_milliseconds

PARALLEL_UPDATES = 0

SensorValue = StateType | datetime
ValueFunction = Callable[[dict[str, Any]], SensorValue]


@dataclass(frozen=True, kw_only=True)
class BlancoSensorEntityDescription(SensorEntityDescription):
    """Describe a BLANCO sensor."""

    value_fn: ValueFunction = field(compare=False)
    availability_key: str
    device_types: frozenset[BlancoDeviceType] | None = None


def _params(data: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a normalized endpoint params dictionary."""
    return data.get(section, {}).get("params") or {}


def _history(data: dict[str, Any], key: str) -> Any:
    """Return one history value."""
    return data.get(DATA_HISTORY, {}).get(key)


def _error_count(data: dict[str, Any], severity: BlancoErrorType) -> int:
    """Count active errors of one severity."""
    return sum(
        1
        for error in data.get(DATA_ERRORS, {}).get("errors", [])
        if error.get("err_type") == severity
    )


def _aqua_remaining_volume(data: dict[str, Any]) -> float | None:
    """Calculate AQUA filter volume remaining from the advertised 2,000 L life."""
    flow = _params(data, DATA_STATUS).get("filter_flow_total")
    if not isinstance(flow, (int, float)) or isinstance(flow, bool):
        return None
    return round(max(0.0, 2000.0 - float(flow) / 1000.0), 1)


def _aqua_remaining_days(data: dict[str, Any]) -> float | None:
    """Calculate AQUA filter days remaining from the advertised 120-day life."""
    age = _params(data, DATA_STATUS).get("filter_age")
    if not isinstance(age, (int, float)) or isinstance(age, bool):
        return None
    return round(max(0.0, 120.0 - float(age) / 24.0), 1)


def _aqua_remaining_percent(data: dict[str, Any]) -> float | None:
    """Return the lower of AQUA filter volume and time remaining."""
    volume = _aqua_remaining_volume(data)
    days = _aqua_remaining_days(data)
    if volume is None or days is None:
        return None
    return round(min(volume / 2000.0, days / 120.0) * 100.0, 1)


_AIO = frozenset({BlancoDeviceType.AIO})
_SODA_AND_AIO = frozenset({BlancoDeviceType.SODA, BlancoDeviceType.AIO})
_HISTORY_DEVICES = frozenset(
    {BlancoDeviceType.SODA, BlancoDeviceType.AIO, BlancoDeviceType.AQUA}
)
_AQUA = frozenset({BlancoDeviceType.AQUA})

SENSOR_DESCRIPTIONS: tuple[BlancoSensorEntityDescription, ...] = (
    BlancoSensorEntityDescription(
        key="online",
        translation_key="online",
        availability_key=DATA_SYSTEM,
        value_fn=lambda data: timestamp_from_milliseconds(
            (data.get(DATA_SYSTEM, {}).get("info") or {}).get("online")
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoSensorEntityDescription(
        key="error_count_critical",
        translation_key="error_count_critical",
        availability_key=DATA_ERRORS,
        value_fn=lambda data: _error_count(data, BlancoErrorType.CRITICAL),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoSensorEntityDescription(
        key="error_count_warning",
        translation_key="error_count_warning",
        availability_key=DATA_ERRORS,
        value_fn=lambda data: _error_count(data, BlancoErrorType.WARNING),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoSensorEntityDescription(
        key="set_point_cooling",
        translation_key="set_point_cooling",
        availability_key=DATA_SETTINGS,
        device_types=_SODA_AND_AIO,
        value_fn=lambda data: _params(data, DATA_SETTINGS).get("set_point_cooling"),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="set_point_heating",
        translation_key="set_point_heating",
        availability_key=DATA_SETTINGS,
        device_types=_AIO,
        value_fn=lambda data: _params(data, DATA_SETTINGS).get("set_point_heating"),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="co2_rest",
        translation_key="co2_rest",
        availability_key=DATA_STATUS,
        device_types=_SODA_AND_AIO,
        value_fn=lambda data: _params(data, DATA_STATUS).get("co2_rest"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="filter_rest",
        translation_key="filter_rest",
        availability_key=DATA_STATUS,
        device_types=_SODA_AND_AIO,
        value_fn=lambda data: _params(data, DATA_STATUS).get("filter_rest"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="filter_remaining_volume",
        translation_key="filter_remaining_volume",
        availability_key=DATA_STATUS,
        device_types=_AQUA,
        value_fn=_aqua_remaining_volume,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=1,
    ),
    BlancoSensorEntityDescription(
        key="filter_remaining_days",
        translation_key="filter_remaining_days",
        availability_key=DATA_STATUS,
        device_types=_AQUA,
        value_fn=_aqua_remaining_days,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="filter_rest_aqua",
        translation_key="filter_rest",
        availability_key=DATA_STATUS,
        device_types=_AQUA,
        value_fn=_aqua_remaining_percent,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="last_dispensing",
        translation_key="last_dispensing",
        availability_key=DATA_ACTIONS,
        device_types=_HISTORY_DEVICES,
        value_fn=lambda data: _history(data, "last_dispense_ml"),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
    BlancoSensorEntityDescription(
        key="last_dispensing_time",
        translation_key="last_dispensing_time",
        availability_key=DATA_ACTIONS,
        device_types=_HISTORY_DEVICES,
        value_fn=lambda data: timestamp_from_milliseconds(
            _history(data, "last_dispense_ts")
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    BlancoSensorEntityDescription(
        key="last_water_type",
        translation_key="last_water_type",
        availability_key=DATA_ACTIONS,
        device_types=_HISTORY_DEVICES,
        value_fn=lambda data: _history(data, "last_water_type"),
        device_class=SensorDeviceClass.ENUM,
        options=["still", "medium", "classic", "hot", "undef"],
    ),
    *tuple(
        BlancoSensorEntityDescription(
            key=f"water_{period}",
            translation_key=f"water_{period}",
            availability_key="stats",
            device_types=_HISTORY_DEVICES,
            value_fn=lambda data, key=f"water_{period}_l": _history(data, key),
            device_class=SensorDeviceClass.WATER,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            suggested_display_precision=2,
        )
        for period in ("today", "week", "month", "year")
    ),
)


def _description_supported(
    coordinator: BlancoDataUpdateCoordinator,
    description: BlancoSensorEntityDescription,
) -> bool:
    """Select device-specific entities while allowing fields discovered at runtime."""
    if (
        description.device_types is None
        or coordinator.dev_type in description.device_types
    ):
        return True
    return description.value_fn(coordinator.data) is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlancoSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if _description_supported(coordinator, description)
    )


class BlancoSensor(BlancoEntity, SensorEntity):
    """Represent one read-only BLANCO value."""

    entity_description: BlancoSensorEntityDescription

    def __init__(
        self,
        coordinator: BlancoDataUpdateCoordinator,
        description: BlancoSensorEntityDescription,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.dev_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return whether the source endpoint's newest request succeeded."""
        return super().available and self.coordinator.endpoint_available(
            self.entity_description.availability_key
        )

    @property
    def native_value(self) -> SensorValue:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attach a bounded, severity-filtered list to error counters."""
        severity_by_key = {
            "error_count_critical": BlancoErrorType.CRITICAL,
            "error_count_warning": BlancoErrorType.WARNING,
        }
        severity = severity_by_key.get(self.entity_description.key)
        if severity is None:
            return None
        matching = [
            error
            for error in self.coordinator.data.get(DATA_ERRORS, {}).get("errors", [])
            if error.get("err_type") == severity
        ][:20]
        return {
            "errors": [
                {
                    "code": error.get("err_code"),
                    "timestamp": (
                        timestamp.isoformat()
                        if (
                            timestamp := timestamp_from_milliseconds(
                                error.get("err_ts")
                            )
                        )
                        else None
                    ),
                }
                for error in matching
            ]
        }
