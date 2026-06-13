"""Tests for YarboMapSensor.

Covers: native_value (feature count), extra_state_attributes (zone summary,
center coordinates), and _handle_coordinator_update dedup logic.
"""

from unittest.mock import MagicMock, patch


from custom_components.yarbo.map_sensor import YarboMapSensor

SN = "SN001"

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"properties": {"zone_type": "work"}},
        {"properties": {"zone_type": "work"}},
        {"properties": {"zone_type": "forbidden"}},
    ],
}


def _make_sensor(map_data=None, gps_refs=None):
    device = MagicMock()
    device.sn = SN
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord.map_data = map_data or {}
    coord.gps_refs = gps_refs or {}

    sensor = YarboMapSensor.__new__(YarboMapSensor)
    sensor._device = device
    sensor.coordinator = coord
    sensor._last_signature = None
    return sensor


# ---------------------------------------------------------------------------
# native_value
# ---------------------------------------------------------------------------


class TestNativeValue:
    def test_returns_feature_count_as_string(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        assert sensor.native_value == "3"

    def test_empty_features(self):
        sensor = _make_sensor(
            map_data={SN: {"type": "FeatureCollection", "features": []}}
        )
        assert sensor.native_value == "0"

    def test_no_map_data_returns_none(self):
        sensor = _make_sensor()
        assert sensor.native_value is None

    def test_missing_sn_returns_none(self):
        sensor = _make_sensor(map_data={"OTHER_SN": GEOJSON})
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


class TestExtraStateAttributes:
    def test_zone_summary(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        attrs = sensor.extra_state_attributes
        assert attrs["zone_summary"] == {"work": 2, "forbidden": 1}
        assert attrs["feature_count"] == 3

    def test_center_included_when_gps_ref_present(self):
        sensor = _make_sensor(
            map_data={SN: GEOJSON},
            gps_refs={SN: {"ref": {"latitude": 37.1, "longitude": -122.0}}},
        )
        attrs = sensor.extra_state_attributes
        assert attrs["latitude"] == 37.1
        assert attrs["longitude"] == -122.0

    def test_center_absent_when_no_gps_ref(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        attrs = sensor.extra_state_attributes
        assert "latitude" not in attrs
        assert "longitude" not in attrs

    def test_empty_when_no_map_data(self):
        sensor = _make_sensor()
        assert sensor.extra_state_attributes == {}

    def test_missing_zone_type_counted_as_unknown(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [{"properties": {}}],
        }
        sensor = _make_sensor(map_data={SN: geojson})
        assert sensor.extra_state_attributes["zone_summary"] == {"unknown": 1}


# ---------------------------------------------------------------------------
# _handle_coordinator_update — dedup
# ---------------------------------------------------------------------------


class TestHandleCoordinatorUpdate:
    def test_writes_state_on_first_call(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        with patch.object(type(sensor), "async_write_ha_state") as mock_write:
            sensor._handle_coordinator_update()
        mock_write.assert_called_once()

    def test_skips_write_when_unchanged(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        with patch.object(type(sensor), "async_write_ha_state") as mock_write:
            sensor._handle_coordinator_update()
            sensor._handle_coordinator_update()
        mock_write.assert_called_once()

    def test_writes_again_when_data_changes(self):
        sensor = _make_sensor(map_data={SN: GEOJSON})
        with patch.object(type(sensor), "async_write_ha_state") as mock_write:
            sensor._handle_coordinator_update()
            sensor.coordinator.map_data = {
                SN: {
                    "type": "FeatureCollection",
                    "features": [{"properties": {"zone_type": "work"}}],
                }
            }
            sensor._handle_coordinator_update()
        assert mock_write.call_count == 2
