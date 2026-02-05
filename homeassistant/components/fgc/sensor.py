from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FgcCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the FGC sensor."""
    coordinator: FgcCoordinator = config_entry.runtime_data
    
    sensors = [
        FgcNextDepartureSensor(coordinator),
        FgcDelaySensor(coordinator),
        FgcStatusSensor(coordinator),
    ]
    async_add_entities(sensors)


class FgcSensorBase(CoordinatorEntity[FgcCoordinator], SensorEntity):
    """Base class for FGC sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FgcCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        # Unique ID based on station-line and sensor type
        self._station = coordinator.station_id
        self._line = coordinator.line_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{self._station}_{self._line}")},
            "name": f"{coordinator.station_name} {self._line}",
            "manufacturer": "FGC",
        }


class FgcNextDepartureSensor(FgcSensorBase):
    """Sensor for the next departure time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_departure"
    _attr_unique_id = "next_departure" # Will be prefixed by device identifier in unique_id property? No, manual unique_id

    def __init__(self, coordinator: FgcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.station_id}_{coordinator.line_name}_next_departure"
        self._attr_name = "Next Departure"

    @property
    def native_value(self):
        """Return the next departure time."""
        # Check for real-time match first
        # We need to correlate schedule with real-time
        # For simplicity, let's take the first scheduled departure and apply delay if matched?
        # OR if we have matched RT updates, take the earliest one?
        
        # Strategy:
        # 1. Get first scheduled departure.
        # 2. Check if there's a RT update for it (requires matching trip_id or logic).
        # Since we don't have robust trip_id matching from schedule yet, 
        # let's fallback to: If RT updates exist, use the earliest RT time.
        # If not, use earliest Schedule time.
        
        rt_updates = self.coordinator.data.get("realtime_updates", [])
        if rt_updates:
            # Sort by time
            # RT updates are stop_time_update objects
            # arrival.time or departure.time
            times = []
            for stu in rt_updates:
                ts = stu.arrival.time if stu.HasField('arrival') else (stu.departure.time if stu.HasField('departure') else 0)
                if ts > 0:
                    # Provide timezone to make it aware
                    times.append(datetime.fromtimestamp(ts, dt_util.DEFAULT_TIME_ZONE))
            
            if times:
                return min(times)

        # Fallback to schedule
        departures = self.coordinator.data.get("departures", [])
        if departures:
            # format "HH:MM:SS"
            time_str = departures[0].get("departure_time")
            if time_str:
                now = dt_util.now()
                # Create timezone-aware datetime from time_str
                # Careful with day rollovers (next day)
                # But API usually returns today's. 
                try:
                    dep_time = datetime.strptime(time_str, "%H:%M:%S").time()
                    dt = now.replace(hour=dep_time.hour, minute=dep_time.minute, second=dep_time.second, microsecond=0)
                    if dt < now:
                        # Maybe it passed or it is for tomorrow? 
                        # API "viajes-de-hoy" implies today.
                        pass
                    return dt
                except ValueError:
                    pass
        
        return None
    
    @property
    def extra_state_attributes(self):
        # Pass full departures list here for power users
        return {
            "departures": self.coordinator.data.get("departures", []),
            "real_time": bool(self.coordinator.data.get("realtime_updates"))
        }


class FgcDelaySensor(FgcSensorBase):
    """Sensor for the delay in minutes."""
    
    _attr_device_class = SensorDeviceClass.DURATION # Or None with Unit minutes
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert"
    _attr_name = "Delay"

    def __init__(self, coordinator: FgcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.station_id}_{coordinator.line_name}_delay"

    @property
    def native_value(self):
        """Return delay of the next train."""
        rt_updates = self.coordinator.data.get("realtime_updates", [])
        if rt_updates:
            # Assume the first one in the list (or nearest time) is the next train
            # Ideally we sort them. Let's pick the one with earliest time
            best_stu = None
            min_ts = float('inf')
            
            for stu in rt_updates:
                ts = stu.arrival.time if stu.HasField('arrival') else (stu.departure.time if stu.HasField('departure') else 0)
                if ts < min_ts:
                    min_ts = ts
                    best_stu = stu
            
            if best_stu:
                delay_sec = best_stu.arrival.delay if best_stu.HasField('arrival') else (best_stu.departure.delay if best_stu.HasField('departure') else 0)
                return round(delay_sec / 60)
        
        return 0 # No delay known


class FgcStatusSensor(FgcSensorBase):
    """Sensor for the text status."""
    
    _attr_name = "Status"
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: FgcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.station_id}_{coordinator.line_name}_status"

    @property
    def native_value(self):
        rt_updates = self.coordinator.data.get("realtime_updates", [])
        if not rt_updates:
            return "Scheduled"
        
        # Calculate delay again (should share logic ideally)
        # Using same logic as DelaySensor
        best_stu = None
        min_ts = float('inf')
        for stu in rt_updates:
            ts = stu.arrival.time if stu.HasField('arrival') else (stu.departure.time if stu.HasField('departure') else 0)
            if ts < min_ts:
                min_ts = ts
                best_stu = stu
        
        delay_min = 0
        if best_stu:
             delay_sec = best_stu.arrival.delay if best_stu.HasField('arrival') else (best_stu.departure.delay if best_stu.HasField('departure') else 0)
             delay_min = round(delay_sec / 60)
             
        if delay_min > 1:
            return "Delayed"
        elif delay_min < -1:
            return "Early"
        else:
            return "On Time"