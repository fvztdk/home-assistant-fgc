import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .fgc_transit import FgcTransit

_LOGGER = logging.getLogger(__name__)


class FgcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.fgc_api = None
        self.selected_line = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step: Line selection."""
        errors = {}

        if not self.fgc_api:
            session = async_get_clientsession(self.hass)
            self.fgc_api = FgcTransit(session)

        if user_input is not None:
            self.selected_line = user_input["line"]
            return await self.async_step_station()

        # Fetch lines from API
        try:
            lines_data = await self.fgc_api.get_lines()
            # Create a dictionary of line_short_name: line_long_name for the dropdown
            # We use route_short_name as the value to store
            lines_dict = {
                line["route_short_name"]: f"{line['route_short_name']} - {line.get('route_long_name', '')}"
                for line in lines_data
            }
            # Sort by key (short name)
            sorted_lines = dict(sorted(lines_dict.items()))
        except Exception:
            errors["base"] = "cannot_connect"
            sorted_lines = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("line", default=list(sorted_lines.keys())[0] if sorted_lines else None): vol.In(sorted_lines),
                }
            ),
            errors=errors,
        )

    async def async_step_station(self, user_input=None):
        """Handle the second step: Station selection."""
        errors = {}

        if user_input is not None:
            station_id = user_input["station"]
            await self.async_set_unique_id(f"{self.selected_line}_{station_id}")
            self._abort_if_unique_id_configured()

            station_name = await self.fgc_api.get_station_name(station_id)
            return self.async_create_entry(
                title=f"{station_name} ({self.selected_line})",
                data={
                    "line": self.selected_line,
                    "station": station_id,
                    "station_name": station_name
                }
            )

        # Get stations for the selected line
        try:
            stations_data = await self.fgc_api.get_stations(self.selected_line)
            _LOGGER.info("DEBUG: stations_data=%s", stations_data)
            
            # Use parent_station as key, stop_name as value
            stations_dict = {
                station["parent_station"]: station["stop_name"]
                for station in stations_data
            }
            sorted_stations = dict(sorted(stations_dict.items(), key=lambda item: item[1]))
        except Exception as e:
            _LOGGER.exception("DEBUG: Failed to get stations: %s", e)
            errors["base"] = "cannot_get_stations"
            sorted_stations = {}

        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required("station"): vol.In(sorted_stations),
                }
            ),
            errors=errors,
        )