"""Map zone sensor platform for Yarbo integration — GeoJSON work zones."""

from __future__ import annotations

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

    entities = [
        YarboMapSensor(coordinator, device)
        for device in coordinator.devices
    ]
    async_add_entities(entities)


class YarboMapSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
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
            f.get("properties", {}).get("zone_type", "unknown")
            for f in features
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
        signature = (self.native_value, repr(self.extra_state_attributes))
        if signature == self._last_signature:
            return
        self._last_signature = signature
        self.async_write_ha_state()

