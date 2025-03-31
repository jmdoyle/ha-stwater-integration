import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import STWaterMeterUpdateCoordinator


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry) -> bool:
    """Set up from a config entry."""
    try:
        _LOGGER.debug("Setting up ST Water integration")
        coordinator = STWaterMeterUpdateCoordinator(hass, entry)
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator

        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        _LOGGER.debug("ST Water integration setup complete")

        return True

    except Exception as err:
        _LOGGER.error("Error setting up ST Water integration: %s", err)
        return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_setup_entry(hass, entry)
