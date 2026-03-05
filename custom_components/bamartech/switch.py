"""Switch platform for the Bamartech integration.

Each switch maps to one bit in byte 2 of the device state packet.
Turning a switch on/off calls coordinator.async_set_output() which
flips the appropriate bit, recalculates the CRC, and publishes the
updated 12-byte frame to the device's MQTT _in topic.

Switches mirror the 4 controls shown in the Bamartech iOS app:
  - Dmuchawa    (Blower / Aeration)
  - Pompa       (Pump)
  - Elektrozawór (Solenoid Valve)
  - Wyjście     (Output)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BITMASK_BLOWER,
    BITMASK_OUTPUT,
    BITMASK_PUMP,
    BITMASK_SOLENOID,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import BamartechCoordinator


@dataclass(frozen=True, kw_only=True)
class BamartechSwitchEntityDescription(SwitchEntityDescription):
    """Extend the base description with coordinator data key and output bitmask."""

    data_key: str = ""
    bitmask: int = 0


# ---------------------------------------------------------------------------
# All four device switches — matching the Bamartech iOS app controls.
# data_key values must match keys returned by coordinator._parse_message().
# ---------------------------------------------------------------------------
SWITCH_DESCRIPTIONS: tuple[BamartechSwitchEntityDescription, ...] = (
    BamartechSwitchEntityDescription(
        key="blower",
        data_key="dmuchawa",
        bitmask=BITMASK_BLOWER,
        name="Dmuchawa",
        icon="mdi:air-filter",
    ),
    BamartechSwitchEntityDescription(
        key="pump",
        data_key="pompa",
        bitmask=BITMASK_PUMP,
        name="Pompa",
        icon="mdi:pump",
    ),
    BamartechSwitchEntityDescription(
        key="solenoid",
        data_key="elektrozawor",
        bitmask=BITMASK_SOLENOID,
        name="Elektrozawór",
        icon="mdi:electric-switch",
    ),
    BamartechSwitchEntityDescription(
        key="output",
        data_key="wyjscie",
        bitmask=BITMASK_OUTPUT,
        name="Wyjście",
        icon="mdi:export",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bamartech switch entities from a config entry."""
    coordinator: BamartechCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BamartechSwitch(coordinator, entry, description)
        for description in SWITCH_DESCRIPTIONS
    )


class BamartechSwitch(CoordinatorEntity[BamartechCoordinator], SwitchEntity):
    """A single Bamartech control switch backed by an output bitmask."""

    _attr_has_entity_name = True
    entity_description: BamartechSwitchEntityDescription

    def __init__(
        self,
        coordinator: BamartechCoordinator,
        entry: ConfigEntry,
        description: BamartechSwitchEntityDescription,
    ) -> None:
        """Initialise the switch."""
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
    def is_on(self) -> bool | None:
        """Return the current on/off state from coordinator data."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self.entity_description.data_key)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the output bit on."""
        await self.coordinator.async_set_output(
            self.entity_description.bitmask, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the output bit."""
        await self.coordinator.async_set_output(
            self.entity_description.bitmask, False
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Push the updated state to the HA state machine."""
        self.async_write_ha_state()
