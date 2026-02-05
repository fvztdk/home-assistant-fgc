from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import FgcCoordinator
from .fgc_transit import FgcTransit

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type FgcConfigEntry = ConfigEntry[FgcCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the FGC component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FgcConfigEntry) -> bool:
    """Set up FGC from a config entry."""
    session = async_get_clientsession(hass)
    client = FgcTransit(session)

    # Test connection
    try:
        await client.get_lines()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to FGC API: {err}") from err

    # Extract config data
    station_id = entry.data["station"]
    station_name = entry.data.get("station_name", station_id)
    line_name = entry.data.get("line")

    # If station name wasn't stored (migration case), try to fetch it
    if "station_name" not in entry.data:
         station_name = await client.get_station_name(station_id)

    coordinator = FgcCoordinator(hass, entry, client, station_id, line_name, station_name)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FgcConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)