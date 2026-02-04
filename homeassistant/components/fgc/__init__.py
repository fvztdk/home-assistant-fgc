from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .fgc_transit import FgcTransit

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type FgcConfigEntry = ConfigEntry[FgcTransit]


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

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FgcConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)