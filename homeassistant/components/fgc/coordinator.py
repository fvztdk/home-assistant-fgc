from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .fgc_transit import FgcTransit

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

class FgcCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FGC data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        fgc_api: FgcTransit,
        station_id: str,
        line_name: str | None,
        station_name: str,
    ) -> None:
        """Initialize the coordinator."""
        self.fgc_api = fgc_api
        self.station_id = station_id
        self.line_name = line_name
        self.station_name = station_name
        
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"FGC {station_name} {line_name}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")

        try:
            # 1. Fetch Scheduled Departures
            departures = await self.fgc_api.get_next_departures(
                self.station_id, self.line_name, time_str
            )

            # 2. Fetch Real-time Updates
            realtime_updates = []
            if self.line_name:
                realtime_updates = await self.fgc_api.get_realtime_updates(self.line_name)

            # 3. Match Real-time to Station
            matched_realtime = []
            if realtime_updates:
                for entity in realtime_updates:
                    if entity.HasField('trip_update'):
                        tu = entity.trip_update
                        for stu in tu.stop_time_update:
                            if stu.stop_id.startswith(self.station_id):
                                matched_realtime.append(stu)
                                # We only need the first match per trip usually, but let's collect all
                                # actually let's structure it so we can easily lookup by trip_id if needed
                                # or just return the list of matched updates for the sensors to parse

            return {
                "departures": departures,
                "realtime_updates": matched_realtime,
                "gtfs_raw": realtime_updates # Keeping raw just in case, though matched is better
            }
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
