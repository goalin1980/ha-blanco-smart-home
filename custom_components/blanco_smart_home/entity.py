"""Base entities for BLANCO Smart Home Cloud."""

from __future__ import annotations

from typing import Any

from blanco_smart_home_api_client import BLANCO_DEVICE_NAMES
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_SYSTEM, DOMAIN
from .coordinator import BlancoDataUpdateCoordinator


class BlancoEntity(CoordinatorEntity[BlancoDataUpdateCoordinator]):
    """Base class shared by all BLANCO entities."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device metadata from the latest system response."""
        params: dict[str, Any] = self.coordinator.data.get(DATA_SYSTEM, {}).get(
            "params", {}
        )
        model = (
            BLANCO_DEVICE_NAMES.get(self.coordinator.dev_type)
            if self.coordinator.dev_type is not None
            else None
        )
        name = params.get("dev_name") or (
            f"BLANCO {model}" if model else "BLANCO water system"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.dev_id)},
            name=name,
            manufacturer="BLANCO",
            model=model,
            serial_number=self.coordinator.serial,
            sw_version=params.get("sw_ver_main_con"),
        )
