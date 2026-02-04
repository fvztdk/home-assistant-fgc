import re
from aioresponses import aioresponses
from homeassistant.components.fgc.const import DOMAIN
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant


async def test_flow_user(hass: HomeAssistant):
    """Test user setup flow."""
    with aioresponses() as m:
        # Mock lines fetching
        m.get(
            "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/lineas-red-fgc/records?limit=100",
            payload={
                "results": [
                    {"route_short_name": "S1", "route_long_name": "Terrassa"},
                    {"route_short_name": "S2", "route_long_name": "Sabadell"}
                ]
            }
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        # Mock stations fetching for S1
        m.get(
            re.compile(r"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records.*"),
            payload={
                "results": [
                    {"parent_station": "PC", "stop_name": "Placa Catalunya"},
                    {"parent_station": "PROV", "stop_name": "Provenca"}
                ]
            }
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"line": "S1"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "station"

        # Mock station name fetching for PC
        m.get(
            re.compile(r"https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/viajes-de-hoy/records.*"),
            payload={
                "results": [
                    {"stop_name": "Placa Catalunya"}
                ]
            }
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"station": "PC"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Placa Catalunya (S1)"
        assert result["data"] == {
            "line": "S1",
            "station": "PC",
            "station_name": "Placa Catalunya",
        }