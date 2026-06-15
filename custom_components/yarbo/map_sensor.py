"""Map zone sensor platform for Yarbo integration — GeoJSON work zones."""

from __future__ import annotations

import json
import logging
from collections import Counter

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YarboDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo map sensor entities."""
    coordinator: YarboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in coordinator.devices:
        entities.append(YarboMapSensor(coordinator, device))
        entities.append(YarboMapGeoJsonSensor(coordinator, device))
    async_add_entities(entities)


class YarboMapSensor(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Sensor entity exposing map zone data as GeoJSON FeatureCollection."""

    _attr_has_entity_name = True
    _attr_name = "Map Zones"
    _attr_icon = "mdi:map"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: YarboDataUpdateCoordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_map_zones"
        self._last_signature: tuple | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    @property
    def native_value(self) -> str | None:
        """Return the number of map features as the sensor value."""
        geojson = self.coordinator.map_data.get(self._device.sn)
        if geojson is None:
            return None
        return str(len(geojson.get("features", [])))

    @property
    def extra_state_attributes(self) -> dict:
        """Expose a lightweight zone summary and center coordinates only.

        The full GeoJSON FeatureCollection is deliberately NOT included here: a
        complex map exceeds Home Assistant's 16 KB attribute limit, which makes
        the recorder skip storage and pushes the whole payload over WebSocket to
        every dashboard on each state write. The frontend fetches the GeoJSON on
        demand via the ``yarbo/map_zones`` WebSocket command instead.
        """
        geojson = self.coordinator.map_data.get(self._device.sn)
        if geojson is None:
            return {}

        features = geojson.get("features", [])
        type_counts = Counter(
            f.get("properties", {}).get("zone_type", "unknown") for f in features
        )

        attrs = {
            "zone_summary": dict(type_counts),
            "feature_count": len(features),
        }

        # Use device GPS reference as center point
        gps_ref = self.coordinator.gps_refs.get(self._device.sn, {})
        ref = gps_ref.get("ref", {})
        if ref.get("latitude") is not None:
            attrs["latitude"] = ref["latitude"]
            attrs["longitude"] = ref["longitude"]

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write HA state only when the map summary actually changes.

        As a CoordinatorEntity this is invoked on every coordinator push (which
        can be frequent). The map data changes rarely, so skip redundant state
        writes to avoid needless recorder rows and dashboard WebSocket traffic.
        """
        signature = (
            self.native_value,
            json.dumps(self.extra_state_attributes, sort_keys=True),
        )
        if signature == self._last_signature:
            return
        self._last_signature = signature
        self.async_write_ha_state()


class YarboMapGeoJsonSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Sensor exposing full GeoJSON map data as entity attributes for Lovelace map cards.

    State = feature count. Attributes = geojson (work/no-go zones) + obstacles_geojson
    (dynamic obstacles from cloud_points_feedback). Disabled by default — large payloads
    may exceed HA's 16 KB attribute limit and should be excluded from the recorder:

        recorder:
          exclude:
            entities:
              - sensor.<sn>_map_geojson
    """

    _attr_has_entity_name = True
    _attr_name = "Map GeoJSON"
    _attr_icon = "mdi:map-search"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False  # keep — large attr, opt-in only

    def __init__(self, coordinator: YarboDataUpdateCoordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_map_geojson"
        self._last_signature: tuple | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    @property
    def native_value(self) -> int | None:
        geojson = self.coordinator.map_data.get(self._device.sn)
        if geojson is None:
            return None
        return len(geojson.get("features", []))

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        geojson = self.coordinator.map_data.get(self._device.sn)
        if geojson is not None:
            attrs["geojson"] = geojson
        cp = self.coordinator.cloud_points.get(self._device.sn)
        if cp:
            from yarbo_robot_sdk.device_helpers import convert_local_to_gps

            gps_ref = self.coordinator.gps_refs.get(self._device.sn) or {}
            ref = gps_ref.get("ref") or {}
            ref_lat = ref.get("latitude")
            ref_lon = ref.get("longitude")
            barriers = cp.get("tmp_barrier_points") or []
            if barriers and ref_lat is not None and ref_lon is not None:
                features = []
                for i, cluster in enumerate(barriers):
                    if not isinstance(cluster, list) or not cluster:
                        continue
                    coords = []
                    for pt in cluster:
                        try:
                            lat, lon = convert_local_to_gps(
                                ref_lat,
                                ref_lon,
                                float(pt.get("x", 0)),
                                float(pt.get("y", 0)),
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
                        {
                            "type": "Feature",
                            "geometry": geom,
                            "properties": {"obstacle_index": i},
                        }
                    )
                if features:
                    attrs["obstacles_geojson"] = {
                        "type": "FeatureCollection",
                        "features": features,
                    }
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        signature = (
            self.native_value,
            id(self.coordinator.map_data.get(self._device.sn)),
        )
        if signature == self._last_signature:
            return
        self._last_signature = signature
        self.async_write_ha_state()
