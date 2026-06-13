"""WebSocket API for Yarbo — on-demand retrieval of large map (GeoJSON) data.

The full GeoJSON work-zone map is intentionally kept out of the ``map_zones``
sensor's state attributes: a complex map can exceed Home Assistant's 16 KB
attribute limit, which makes the recorder skip storage (logging a repeated
warning) and pushes the whole payload over WebSocket to every dashboard on each
state write. The frontend instead fetches the map on demand through the
``yarbo/map_zones`` command, which returns the GeoJSON straight from the
coordinator's in-memory cache only when a card actually needs it.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

WS_TYPE_MAP_ZONES = "yarbo/map_zones"
_REGISTERED_KEY = "yarbo_ws_registered"


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register Yarbo WebSocket commands once per Home Assistant instance."""
    if hass.data.get(_REGISTERED_KEY):
        return
    websocket_api.async_register_command(hass, _handle_map_zones)
    hass.data[_REGISTERED_KEY] = True


@websocket_api.websocket_command(  # type: ignore[attr-defined]
    {
        vol.Required("type"): WS_TYPE_MAP_ZONES,
        vol.Required("sn"): str,
    }
)
@callback
def _handle_map_zones(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,  # type: ignore[attr-defined]
    msg: dict[str, Any],
) -> None:
    """Return the full GeoJSON map and center coordinate for a device serial."""
    sn = msg["sn"]
    for coordinator in hass.data.get(DOMAIN, {}).values():
        geojson = coordinator.map_data.get(sn)
        if geojson is None:
            continue

        ref = coordinator.gps_refs.get(sn, {}).get("ref", {})
        center = None
        if ref.get("latitude") is not None:
            center = {
                "latitude": ref["latitude"],
                "longitude": ref["longitude"],
            }

        connection.send_result(
            msg["id"],
            {"sn": sn, "geojson": geojson, "center": center},
        )
        return

    connection.send_error(
        msg["id"],
        websocket_api.const.ERR_NOT_FOUND,
        f"No map data available for sn={sn}",
    )
