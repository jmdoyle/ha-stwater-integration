import asyncio
import logging
import time
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.recorder.statistics import async_add_external_statistics, get_last_statistics
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from .stw_consumption import get_water_usage
from .const import DOMAIN, SCAN_INTERVAL, DEBUG_MODE, NAME, CONSUMPTION_NAME, CONF_SELENIUM
from .util import async_load_debug_data
from homeassistant.components.recorder import get_instance
from operator import itemgetter

_LOGGER = logging.getLogger(__name__)


class STWaterMeterUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ST Water data."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self._entry = entry
        self._current_data = None

    async def _async_update_data(self):
        """Fetch data from ST Water website."""
        try:
            await self.insert_statistics()
        except Exception as err:
            _LOGGER.error("Error updating water consumption data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}")


    async def insert_statistics(self):
        """Insert statistics into recorder."""
        start_time = time.time()
        statistic_id = f"{DOMAIN}:consumption"
        _LOGGER.info("Fetching water consumption data")
        try:
            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {
                    "sum"}
            )
            if len(last_stats.get(statistic_id, [])) > 0:
                last_stats = last_stats[statistic_id]
                last_stats = sorted(last_stats, key=itemgetter("start"), reverse=False)[0]
        except AttributeError:
            last_stats = None
        _LOGGER.debug("last_stats: %s", last_stats)

        if DEBUG_MODE:
            _LOGGER.debug("Debug mode is enabled, loading debug data")
            self._current_data = await async_load_debug_data(self.hass)
            if not self._current_data:
                raise UpdateFailed("No debug data available")
        else:
            try:
                async with asyncio.timeout(120):
                    _LOGGER.debug("Fetching data from ST Water website")
                    self._current_data = await self.hass.async_add_executor_job(
                        get_water_usage,
                        self._entry.data[CONF_USERNAME],
                        self._entry.data[CONF_PASSWORD],
                        self._entry.data[CONF_SELENIUM],
                    )
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout while fetching water consumption data")
                raise UpdateFailed("Data fetch timed out")

        _LOGGER.info(
            "Finished fetching st_water data in %.3f seconds (success: %s)",
            time.time() - start_time,
            bool(self._current_data),
        )

        if not self._current_data:
            raise UpdateFailed("No data received")

        statistics = []
        running_total = 0
        if last_stats:
            running_total = last_stats["sum"]
        _LOGGER.debug("running_total: %s", running_total)
        hourly_consumption_data = sorted(self._current_data.keys())
        _LOGGER.debug("hourly_consumption_data: %s", hourly_consumption_data)
        for date_str in hourly_consumption_data:
            # Skip dates that are already in the database
            if last_stats and datetime.strptime(date_str, '%Y-%m-%d') < datetime.fromtimestamp(last_stats["end"]).replace(hour=0, minute=0, second=0, microsecond=0):
                _LOGGER.debug("Skipping date: %s", date_str)
                continue
            hours = self._current_data[date_str]
            for hour_str, value in sorted(hours.items()):
                start = dt_util.as_utc(datetime.strptime(f"{date_str} {hour_str}", "%Y-%m-%d %H:%M"))
                running_total += float(value)
                statistics.append(
                    StatisticData(
                        start=start,
                        state=float(value),
                        sum=running_total
                    )
                )

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"{NAME} {CONSUMPTION_NAME}",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement="L",
        )

        if statistics:
            try:
                async_add_external_statistics(self.hass, metadata, statistics)
            except Exception as stats_err:
                _LOGGER.error("Failed to record statistics: %s", stats_err)