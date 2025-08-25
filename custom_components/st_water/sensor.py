"""Sensor platform for ST Water integration."""
import logging
from typing import Optional, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, MANUFACTURER, MODEL, CONSUMPTION_NAME
from .coordinator import STWaterMeterUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ST Water sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Add consumption sensor
    async_add_entities([STWaterConsumptionSensor(coordinator, entry)])


class STWaterConsumptionSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ST Water consumption sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "L"

    def __init__(
        self, coordinator: STWaterMeterUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_consumption"
        self._attr_name = CONSUMPTION_NAME
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> Optional[Any]:
        """Return the state of the sensor."""
        # This will be updated when statistics are added by the coordinator
        return None  # The value is stored in statistics