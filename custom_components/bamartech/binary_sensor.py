"""Binary sensor platform for the Bamartech integration.

Provides a single overall plant-health binary sensor:

  plant_ok = True   when MQTT is connected and a state packet has been received
  plant_ok = False  when MQTT is disconnected

Uses device_class=PROBLEM so Home Assistant treats the values as:
  is_on=False  → no problem  (green / OK)   ← normal running state
  is_on=True   → problem     (red / alert)  ← MQTT disconnected
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .coordinator import BamartechCoordinator


@dataclass(frozen=True, kw_only=True)
class BamartechBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Extend the base description with a coordinator data key."""

    data_key: str = ""


BINARY_SENSOR_DESCRIPTIONS: tuple[BamartechBinarySensorEntityDescription, ...] = (
    BamartechBinarySensorEntityDescription(
        key="plant_ok",
        data_key="plant_ok",
        name="Status Oczyszczalni",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:water-check",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bamartech binary sensor entities from a config entry."""
    coordinator: BamartechCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BamartechBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class BamartechBinarySensor(CoordinatorEntity[BamartechCoordinator], BinarySensorEntity):
    """Overall plant health binary sensor — True when connected."""

    _attr_has_entity_name = True
    entity_description: BamartechBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BamartechCoordinator,
        entry: ConfigEntry,
        description: BamartechBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return True (= PROBLEM) when the plant is not connected.

        plant_ok in coordinator data is True only when MQTT is live and
        a state packet has been received.  We invert it here because
        device_class=PROBLEM means is_on=True → alert.
        """
        if self.coordinator.data is None:
            return None
        plant_ok = self.coordinator.data.get(self.entity_description.data_key)
        if plant_ok is None:
            return None
        # plant_ok True  → connected → no problem → return False
        # plant_ok False → disconnected → problem  → return True
        return not bool(plant_ok)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push the updated value to the HA state machine."""
        self.async_write_ha_state()
