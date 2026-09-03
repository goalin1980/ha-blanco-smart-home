"""Binary sensor entities for BLANCO Smart Home Cloud."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from blanco_smart_home_api_client import BlancoDeviceType, BlancoErrorType
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BlancoConfigEntry
from .const import DATA_ERRORS, DATA_SETTINGS, DATA_SYSTEM
from .coordinator import BlancoDataUpdateCoordinator
from .entity import BlancoEntity
from .helpers import api_bool, timestamp_from_milliseconds

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlancoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a BLANCO binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None] = field(compare=False)
    availability_key: str
    device_types: frozenset[BlancoDeviceType] | None = None


def _has_problem(data: dict[str, Any]) -> bool:
    """Return whether BLANCO reports a critical error or warning."""
    return any(
        error.get("err_type") in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
        for error in data.get(DATA_ERRORS, {}).get("errors", [])
    )


def _setting(data: dict[str, Any], key: str) -> Any:
    """Return one normalized setting value."""
    return (data.get(DATA_SETTINGS, {}).get("params") or {}).get(key)


def _hot_water_enabled(data: dict[str, Any]) -> bool | None:
    """Expose the inverse child-protection flag as an intuitive state."""
    child_protection = api_bool(_setting(data, "child_protect"))
    return None if child_protection is None else not child_protection


_AIO = frozenset({BlancoDeviceType.AIO})

BINARY_SENSOR_DESCRIPTIONS: tuple[BlancoBinarySensorEntityDescription, ...] = (
    BlancoBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        availability_key=DATA_SYSTEM,
        value_fn=lambda data: api_bool(
            (data.get(DATA_SYSTEM, {}).get("info") or {}).get("connected")
        ),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoBinarySensorEntityDescription(
        key="has_problem",
        translation_key="has_problem",
        availability_key=DATA_ERRORS,
        value_fn=_has_problem,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoBinarySensorEntityDescription(
        key="absence_mode",
        translation_key="absence_mode",
        availability_key=DATA_SETTINGS,
        device_types=_AIO,
        value_fn=lambda data: api_bool(_setting(data, "absence_mode_active")),
    ),
    BlancoBinarySensorEntityDescription(
        key="hot_water_enabled",
        translation_key="hot_water_enabled",
        availability_key=DATA_SETTINGS,
        device_types=_AIO,
        value_fn=_hot_water_enabled,
    ),
)


def _description_supported(
    coordinator: BlancoDataUpdateCoordinator,
    description: BlancoBinarySensorEntityDescription,
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
    """Set up BLANCO binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlancoBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if _description_supported(coordinator, description)
    )


class BlancoBinarySensor(BlancoEntity, BinarySensorEntity):
    """Represent one read-only BLANCO boolean value."""

    entity_description: BlancoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BlancoDataUpdateCoordinator,
        description: BlancoBinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return the current binary value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attach a bounded error list to the problem sensor."""
        if self.entity_description.key != "has_problem":
            return None
        return {
            "errors": [
                {
                    "code": error.get("err_code"),
                    "severity": getattr(error.get("err_type"), "name", "UNDEF"),
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
                for error in self.coordinator.data.get(DATA_ERRORS, {}).get(
                    "errors", []
                )[:20]
            ]
        }
