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
from yarbo_robot_sdk.device_helpers import convert_local_to_gps

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

        obstacles_geojson = _build_obstacles_geojson(
            coordinator.cloud_points.get(sn) or {}, ref
        )

        connection.send_result(
            msg["id"],
            {
                "sn": sn,
                "geojson": geojson,
                "center": center,
                "obstacles_geojson": obstacles_geojson,
            },
        )
        return

    connection.send_error(
        msg["id"],
        websocket_api.const.ERR_NOT_FOUND,
        f"No map data available for sn={sn}",
    )


def _build_obstacles_geojson(cloud_points: dict, ref: dict) -> dict | None:
    """Project cloud_points_feedback barrier clusters to GPS GeoJSON features."""
    barriers = cloud_points.get("tmp_barrier_points") or []
    ref_lat = ref.get("latitude")
    ref_lon = ref.get("longitude")
    if not barriers or ref_lat is None or ref_lon is None:
        return None
    features = []
    for i, cluster in enumerate(barriers):
        if not isinstance(cluster, list) or not cluster:
            continue
        coords = []
        for pt in cluster:
            try:
                lat, lon = convert_local_to_gps(
                    ref_lat, ref_lon, float(pt.get("x", 0)), float(pt.get("y", 0))
                )
                coords.append([round(lon, 7), round(lat, 7)])
            except Exception:  # noqa: BLE001
                pass
        if not coords:
            continue
        geom = (
            {"type": "Point", "coordinates": coords[0]}
            if len(coords) == 1
            else {"type": "MultiPoint", "coordinates": coords}
        )
        features.append(
            {"type": "Feature", "geometry": geom, "properties": {"obstacle_index": i}}
        )
    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}
