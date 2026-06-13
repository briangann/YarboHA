"""Tests for YarboDeviceTracker.

Covers: available, extra_state_attributes, _handle_coordinator_update
(GPS conversion, missing ref, missing odometry, bad values).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.yarbo.device_tracker import YarboDeviceTracker

SN = "SN001"


def _make_tracker(gps_refs=None, device_data=None):
    device = MagicMock()
    device.sn = SN
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord.gps_refs = gps_refs or {}
    coord.data = {SN: device_data} if device_data is not None else {}

    tracker = YarboDeviceTracker.__new__(YarboDeviceTracker)
    tracker._device = device
    tracker.coordinator = coord
    tracker._computed_lat = None
    tracker._computed_lon = None
    return tracker


# ---------------------------------------------------------------------------
# available
# ---------------------------------------------------------------------------


class TestAvailable:
    def test_available_when_rtk_fixed(self):
        tracker = _make_tracker(gps_refs={SN: {"rtkFixType": 1}})
        assert tracker.available is True

    def test_unavailable_when_no_gps_ref(self):
        tracker = _make_tracker()
        assert tracker.available is False

    def test_unavailable_when_rtk_not_fixed(self):
        tracker = _make_tracker(gps_refs={SN: {"rtkFixType": 0}})
        assert tracker.available is False

    def test_unavailable_when_rtk_type_2(self):
        tracker = _make_tracker(gps_refs={SN: {"rtkFixType": 2}})
        assert tracker.available is False


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


class TestExtraStateAttributes:
    def test_gps_ref_in_attrs(self):
        tracker = _make_tracker(
            gps_refs={
                SN: {"rtkFixType": 1, "ref": {"latitude": 37.0, "longitude": -122.0}}
            },
            device_data={"CombinedOdom": {"x": 1.0, "y": 2.0, "phi": 0.5}},
        )
        attrs = tracker.extra_state_attributes
        assert attrs["gps_ref_latitude"] == 37.0
        assert attrs["gps_ref_longitude"] == -122.0
        assert attrs["rtk_fix_type"] == 1

    def test_odometry_in_attrs(self):
        tracker = _make_tracker(
            device_data={"CombinedOdom": {"x": 3.0, "y": 4.0, "phi": 1.2}},
        )
        attrs = tracker.extra_state_attributes
        assert attrs["position_x"] == 3.0
        assert attrs["position_y"] == 4.0
        assert attrs["heading"] == 1.2

    def test_missing_data_returns_none_values(self):
        tracker = _make_tracker()
        attrs = tracker.extra_state_attributes
        assert attrs["position_x"] is None
        assert attrs["position_y"] is None


# ---------------------------------------------------------------------------
# _handle_coordinator_update — GPS conversion
# ---------------------------------------------------------------------------


class TestHandleCoordinatorUpdate:
    def test_no_gps_ref_clears_position(self):
        tracker = _make_tracker()
        tracker._computed_lat = 37.0
        tracker._computed_lon = -122.0
        with patch.object(type(tracker), "async_write_ha_state"):
            tracker._handle_coordinator_update()
        assert tracker._computed_lat is None
        assert tracker._computed_lon is None

    def test_rtk_not_fixed_clears_position(self):
        tracker = _make_tracker(gps_refs={SN: {"rtkFixType": 0}})
        tracker._computed_lat = 37.0
        with patch.object(type(tracker), "async_write_ha_state"):
            tracker._handle_coordinator_update()
        assert tracker._computed_lat is None

    def test_missing_ref_lat_clears_position(self):
        tracker = _make_tracker(gps_refs={SN: {"rtkFixType": 1, "ref": {}}})
        with patch.object(type(tracker), "async_write_ha_state"):
            tracker._handle_coordinator_update()
        assert tracker._computed_lat is None

    def test_missing_odometry_clears_position(self):
        tracker = _make_tracker(
            gps_refs={
                SN: {"rtkFixType": 1, "ref": {"latitude": 37.0, "longitude": -122.0}}
            },
        )
        with patch.object(type(tracker), "async_write_ha_state"):
            tracker._handle_coordinator_update()
        assert tracker._computed_lat is None

    def test_successful_gps_conversion(self):
        tracker = _make_tracker(
            gps_refs={
                SN: {"rtkFixType": 1, "ref": {"latitude": 37.0, "longitude": -122.0}}
            },
            device_data={"CombinedOdom": {"x": 0.0, "y": 0.0}},
        )
        fake_lat, fake_lon = 37.0001, -121.9999
        with patch.object(type(tracker), "async_write_ha_state"):
            with patch(
                "yarbo_robot_sdk.device_helpers.convert_local_to_gps",
                return_value=(fake_lat, fake_lon),
            ):
                tracker._handle_coordinator_update()
        assert tracker._computed_lat == pytest.approx(fake_lat)
        assert tracker._computed_lon == pytest.approx(fake_lon)

    def test_conversion_error_leaves_position_none(self):
        tracker = _make_tracker(
            gps_refs={
                SN: {"rtkFixType": 1, "ref": {"latitude": 37.0, "longitude": -122.0}}
            },
            device_data={"CombinedOdom": {"x": "bad", "y": "data"}},
        )
        with patch.object(type(tracker), "async_write_ha_state"):
            with patch(
                "yarbo_robot_sdk.device_helpers.convert_local_to_gps",
                side_effect=ValueError("bad coords"),
            ):
                tracker._handle_coordinator_update()
        assert tracker._computed_lat is None
