"""Sensor platform for the Bamartech integration.

Exposes four numeric sensors derived from the device state packet:

  uptime_days   — total machine uptime in days
  wywoz_osadow  — sludge-removal countdown in weeks
  biopreparaty  — bio-preparation countdown in days  (reset value: 28)
  konserwacja   — maintenance countdown in weeks
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .coordinator import BamartechCoordinator


@dataclass(frozen=True, kw_only=True)
class BamartechSensorEntityDescription(SensorEntityDescription):
    """Extend the base description with a coordinator data key."""

    data_key: str = ""


SENSOR_DESCRIPTIONS: tuple[BamartechSensorEntityDescription, ...] = (
    BamartechSensorEntityDescription(
        key="uptime_days",
        data_key="uptime_days",
        name="Czas pracy",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BamartechSensorEntityDescription(
        key="wywoz_osadow",
        data_key="wywoz_osadow",
        name="Wywóz osadów",
        icon="mdi:delete-clock",
        native_unit_of_measurement=UnitOfTime.WEEKS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BamartechSensorEntityDescription(
        key="biopreparaty",
        data_key="biopreparaty",
        name="Biopreparaty",
        icon="mdi:flask",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BamartechSensorEntityDescription(
        key="konserwacja",
        data_key="konserwacja",
        name="Konserwacja",
        icon="mdi:wrench-clock",
        native_unit_of_measurement=UnitOfTime.WEEKS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bamartech sensor entities from a config entry."""
    coordinator: BamartechCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BamartechSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BamartechSensor(CoordinatorEntity[BamartechCoordinator], SensorEntity):
    """A single Bamartech numeric sensor."""

    _attr_has_entity_name = True
    entity_description: BamartechSensorEntityDescription

    def __init__(
        self,
        coordinator: BamartechCoordinator,
        entry: ConfigEntry,
        description: BamartechSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Bamartech",
            manufacturer="Bamartech",
            model="Oczyszczalnia",
            configuration_url=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
        )

    @property
    def available(self) -> bool:
        """Mark entity unavailable when MQTT is disconnected."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get("connected", False))

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the latest coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push the updated value to the HA state machine."""
        self.async_write_ha_state()
