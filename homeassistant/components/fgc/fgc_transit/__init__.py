import aiohttp
import asyncio
import logging
from google.transit import gtfs_realtime_pb2

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets"

class FgcTransit:
    def __init__(self, session: aiohttp.ClientSession, gtfs_path=None):
        self._session = session

    async def get_lines(self):
        """Return a list of lines."""
        url = f"{API_BASE}/lineas-red-fgc/records"
        params = {"limit": "100"}
        try:
            async with self._session.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("results", [])
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            return []

    async def get_stations(self, line_name):
        """Return a list of stations for a specific line."""
        url = f"{API_BASE}/viajes-de-hoy/records"
        params = {
            "select": "parent_station, stop_name",
            "where": f'route_short_name="{line_name}"',
            "group_by": "parent_station, stop_name",
            "limit": "100"
        }
        try:
            async with self._session.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("results", [])
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            return []

    async def get_station_name(self, station_id: str):
        """Get station name from station_id (parent_station)."""
        url = f"{API_BASE}/viajes-de-hoy/records"
        params = {
            "select": "stop_name",
            "where": f'parent_station="{station_id}"',
            "limit": "1"
        }
        try:
            async with self._session.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                results = data.get("results", [])
                if results:
                    return results[0]["stop_name"]
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            pass
        return station_id

    async def get_next_departures(self, station_id: str, line_name: str, time_str: str):
        """Get next departures for a given station (parent_station) and line."""
        url = f"{API_BASE}/viajes-de-hoy/records"
        # Filter by parent_station to capture all platforms (both directions)
        where_clause = f'parent_station="{station_id}" AND route_short_name="{line_name}" AND departure_time >= "{time_str}"'

        params = {
            "where": where_clause,
            "order_by": "departure_time",
            "limit": "10"
        }

        try:
            async with self._session.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("results", [])
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError):
            return []

    async def get_realtime_updates(self, line_name: str):
        """Get real-time updates for a specific line."""
        # First, get the URL for the PB file
        url = f"{API_BASE}/trip-updates-gtfs_realtime/records"
        params = {"limit": "1"}
        
        try:
            async with self._session.get(url, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                results = data.get("results", [])
                if not results:
                    return []
                
                # The file URL is usually in a nested structure or a direct link depending on the dataset
                pb_url = results[0].get("file", {}).get("url")
                if not pb_url:
                    _LOGGER.debug("No PB file URL found in trip-updates response")
                    return []
                    
                # Now fetch the PB file
                async with self._session.get(pb_url, timeout=10) as pb_resp:
                    pb_resp.raise_for_status()
                    content = await pb_resp.read()
                    
                    # Parse the content
                    feed = gtfs_realtime_pb2.FeedMessage()
                    feed.ParseFromString(content)
                    
                    updates = []
                    # _LOGGER.debug("Parsed %d entities from GTFS-RT feed", len(feed.entity))
                    
                    for entity in feed.entity:
                        if entity.HasField('trip_update'):
                            # route_id is often empty in this feed, so we return all updates
                            # and let the sensor filter by station/stop_id.
                            updates.append(entity)
                            
                    return updates

        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError, Exception) as err:
             _LOGGER.error("Error fetching real-time updates: %s", err)
             return []