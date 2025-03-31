import json
import logging
from pathlib import Path
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_load_debug_data(hass: HomeAssistant):
    """Load debug data from JSON file asynchronously."""
    try:
        debug_file = Path(f"{hass.config.config_dir}/data/usage_data.json")
        if debug_file.exists():
            return await hass.async_add_executor_job(_load_json_file, debug_file)
    except Exception as err:
        _LOGGER.error("Failed to load debug data: %s", err)
    return None


def _load_json_file(file_path: Path):
    """Load JSON file synchronously (to be run in executor)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
