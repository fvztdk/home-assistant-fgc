from datetime import datetime, timedelta
import logging

from homeassistant.helpers.entity import Entity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the FGC sensor."""
    station_id = config_entry.data["station"]
    station_name = config_entry.data.get("station_name", station_id)
    line_name = config_entry.data.get("line")
    
    fgc_api = config_entry.runtime_data
    
    # If station name wasn't stored (migration case), try to fetch it
    if "station_name" not in config_entry.data:
        station_name = await fgc_api.get_station_name(station_id)

    sensors = [FgcSensor(fgc_api, station_id, station_name, line_name)]
    async_add_entities(sensors, update_before_add=True)


class FgcSensor(Entity):
    """Representation of an FGC sensor."""

    def __init__(self, fgc_api, station_id, station_name, line_name):
        """Initialize the sensor."""
        self._fgc_api = fgc_api
        self._station_id = station_id
        self._line_name = line_name
        self._name = f"{station_name} {line_name}" if line_name else station_name
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Fetch new state data for the sensor."""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")

        _LOGGER.debug("Updating FGC sensor %s. Station ID: %s, Line: %s", self._name, self._station_id, self._line_name)

        # Fetch scheduled departures
        departures = await self._fgc_api.get_next_departures(
            self._station_id, self._line_name, time_str
        )
        _LOGGER.debug("Scheduled departures found: %d", len(departures))
        
        # Fetch real-time updates
        realtime_updates = await self._fgc_api.get_realtime_updates(self._line_name)
        _LOGGER.debug("Real-time updates fetched: %d", len(realtime_updates))
        
        # Process real-time updates
        processed_realtime = []
        if realtime_updates:
            for entity in realtime_updates:
                if entity.HasField('trip_update'):
                    tu = entity.trip_update
                    # Log first few to check matching logic
                    for stu in tu.stop_time_update:
                        # RT stop_id usually includes platform (e.g., GR1, GR2), while station_id is parent (GR)
                        if stu.stop_id.startswith(self._station_id):
                             # Calculate values
                             delay_sec = stu.arrival.delay if stu.HasField('arrival') else (stu.departure.delay if stu.HasField('departure') else 0)
                             timestamp = stu.arrival.time if stu.HasField('arrival') else (stu.departure.time if stu.HasField('departure') else 0)
                             
                             # Format for readability
                             time_obj = datetime.fromtimestamp(timestamp)
                             time_readable = time_obj.strftime("%H:%M:%S")
                             
                             delay_min = round(delay_sec / 60)
                             if delay_min > 0:
                                 delay_readable = f"+{delay_min} min"
                             elif delay_min < 0:
                                 delay_readable = f"{delay_min} min"
                             else:
                                 delay_readable = "On time"

                             processed_realtime.append({
                                 "trip_id": tu.trip.trip_id,
                                 "delay": delay_sec,
                                 "time": timestamp,
                                 "time_readable": time_readable,
                                 "delay_readable": delay_readable
                             })

        if departures:
            # departures is a list of dicts from the API
            next_departure = departures[0]
            self._state = next_departure.get("departure_time")
            
            # Enrich with real-time if we can match or just expose it
            self._attributes["departures"] = departures
            self._attributes["realtime_info"] = processed_realtime
        else:
            self._state = None
            self._attributes["departures"] = []
            self._attributes["realtime_info"] = list(processed_realtime) if processed_realtime else []
            
        _LOGGER.debug("Update complete. State: %s, RT Info count: %d", self._state, len(self._attributes.get("realtime_info", [])))