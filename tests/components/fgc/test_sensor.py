import re
from aioresponses import aioresponses
from homeassistant.components.fgc.const import DOMAIN
from tests.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_sensor_creation(hass: HomeAssistant):
    """Test sensor creation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "station": "PC",
            "station_name": "Placa Catalunya",
            "line": "S1"
        }
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        # Mock connection check (get_lines)
        m.get(
            "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/lineas-red-fgc/records?limit=100",
            payload={"results": []}
        )
        
        # Mock the departure data (dynamic URL)
        m.get(
            re.compile(r"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records.*"),
            payload={
                "results": [
                    {
                        "departure_time": "20:00:00",
                        "stop_name": "Placa Catalunya",
                        "route_short_name": "S1"
                    }
                ]
            }
        )

        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.placa_catalunya_s1")
    assert state
    assert state.state == "20:00:00"


async def test_sensor_update_error(hass: HomeAssistant):
    """Test sensor update with API error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "station": "PC",
            "station_name": "Placa Catalunya",
            "line": "S1"
        }
    )
    entry.add_to_hass(hass)

    with aioresponses() as m:
        # Mock connection check
        m.get(
            "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/lineas-red-fgc/records?limit=100",
            payload={"results": []}
        )
        
        # Initial successful update
        m.get(
            re.compile(r"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records.*"),
            payload={"results": []}
        )

        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Simulate invalid JSON response
        m.get(
            re.compile(r"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records.*"),
            body="invalid json"
        )
        
        # Trigger update
        await async_setup_component(hass, "homeassistant", {})
        await hass.async_block_till_done()
        await hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "sensor.placa_catalunya_s1"}, blocking=True
        )