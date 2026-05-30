"""Tests for raw telemetry sensors (WheelSpeedMSG, RunningStatusMSG, etc.)."""

import pytest

from unittest.mock import MagicMock

from custom_components.yarbo_bg.sensor import (
    YarboChuteSensor,
    YarboGyroRollSensor,
    YarboGyroPitchSensor,
    YarboOdomConfidenceSensor,
    YarboOdometryLeftSensor,
    YarboOdometryRightSensor,
    YarboProximityCenterSensor,
    YarboProximityLeftSensor,
    YarboProximityRightSensor,
    YarboRainSensor,
    YarboSpeedSensor,
)

SN = "DEVICE_SN"


def _device():
    d = MagicMock()
    d.sn = SN
    d.name = "Yarbo Test"
    d.model = "Y1000"
    return d


def _coord(device_data: dict):
    c = MagicMock()
    c.data = {SN: device_data}
    return c


def _make(cls, device_data: dict):
    """Instantiate a sensor by-passing HA's CoordinatorEntity.__init__."""
    sensor = object.__new__(cls)
    sensor.coordinator = _coord(device_data)
    sensor._device = _device()
    return sensor


# ── Speed ─────────────────────────────────────────────────────────────────────


class TestYarboSpeedSensor:
    def test_average_speed(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0.5, "right": 0.51}})
        assert s.native_value == pytest.approx(0.505, abs=1e-3)

    def test_zero_speed(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0.0, "right": 0.0}})
        assert s.native_value == 0.0

    def test_missing_wheel_msg(self):
        s = _make(YarboSpeedSensor, {})
        assert s.native_value is None

    def test_partial_wheel_msg(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0.5}})
        assert s.native_value is None


# ── Odometry ──────────────────────────────────────────────────────────────────


class TestYarboOdometrySensors:
    def test_left_distance(self):
        s = _make(YarboOdometryLeftSensor, {"WheelSpeedMSG": {"dist_left": 1234.567}})
        assert s.native_value == pytest.approx(1234.6, abs=0.1)

    def test_right_distance(self):
        s = _make(YarboOdometryRightSensor, {"WheelSpeedMSG": {"dist_right": 999.1}})
        assert s.native_value == pytest.approx(999.1, abs=0.1)

    def test_missing_returns_none(self):
        s = _make(YarboOdometryLeftSensor, {})
        assert s.native_value is None


# ── Positioning confidence ────────────────────────────────────────────────────


class TestYarboOdomConfidenceSensor:
    def test_confidence_value(self):
        s = _make(YarboOdomConfidenceSensor, {"combined_odom_confidence": 0.9151})
        assert s.native_value == pytest.approx(0.915, abs=1e-3)

    def test_missing_returns_none(self):
        s = _make(YarboOdomConfidenceSensor, {})
        assert s.native_value is None


# ── Rain sensor ───────────────────────────────────────────────────────────────


class TestYarboRainSensor:
    def test_rain_value(self):
        s = _make(YarboRainSensor, {"RunningStatusMSG": {"rain_sensor_data": 23}})
        assert s.native_value == 23.0

    def test_zero_rain(self):
        s = _make(YarboRainSensor, {"RunningStatusMSG": {"rain_sensor_data": 0}})
        assert s.native_value == 0.0

    def test_missing_returns_none(self):
        s = _make(YarboRainSensor, {})
        assert s.native_value is None


# ── Chute angle (Snow Blower only) ───────────────────────────────────────────


class TestYarboChuteSensor:
    def _make_with_head(self, head_type: int | None, chute_angle=45):
        head_msg = {} if head_type is None else {"head_type": head_type}
        data = {
            "HeadMsg": head_msg,
            "RunningStatusMSG": {"chute_angle": chute_angle},
        }
        s = object.__new__(YarboChuteSensor)
        s.coordinator = _coord(data)
        s._device = _device()
        return s

    def test_value_with_snow_blower(self):
        s = self._make_with_head(head_type=1, chute_angle=90)
        assert s.native_value == 90.0

    def test_available_with_snow_blower(self):
        s = self._make_with_head(head_type=1)
        # super().available is MagicMock (truthy), head check passes
        assert s.available is True

    def test_unavailable_with_mower(self):
        s = self._make_with_head(head_type=3)
        assert s.available is False

    def test_unavailable_with_mower_pro(self):
        s = self._make_with_head(head_type=5)
        assert s.available is False

    def test_available_when_head_type_unknown(self):
        # head_type not yet received — default to available
        s = self._make_with_head(head_type=None)
        assert s.available is True


# ── Proximity ─────────────────────────────────────────────────────────────────


class TestYarboProximitySensors:
    def _data(self, lf=9999, mt=9999, rf=9999):
        return {"ultrasonic_msg": {"lf_dis": lf, "mt_dis": mt, "rf_dis": rf}}

    def test_left_clear(self):
        s = _make(YarboProximityLeftSensor, self._data(lf=9999))
        assert s.native_value == 9999.0

    def test_center_obstacle(self):
        s = _make(YarboProximityCenterSensor, self._data(mt=250))
        assert s.native_value == 250.0

    def test_right_obstacle(self):
        s = _make(YarboProximityRightSensor, self._data(rf=180))
        assert s.native_value == 180.0

    def test_missing_ultrasonic_msg(self):
        s = _make(YarboProximityLeftSensor, {})
        assert s.native_value is None


# ── Gyro (disabled by default) ────────────────────────────────────────────────


class TestYarboGyroSensors:
    def test_pitch_value(self):
        s = _make(
            YarboGyroPitchSensor, {"RunningStatusMSG": {"head_gyro_pitch": 1.0237}}
        )
        assert s.native_value == pytest.approx(1.024, abs=1e-3)

    def test_roll_value(self):
        s = _make(
            YarboGyroRollSensor, {"RunningStatusMSG": {"head_gyro_roll": -1.4416}}
        )
        assert s.native_value == pytest.approx(-1.442, abs=1e-3)

    def test_pitch_missing(self):
        s = _make(YarboGyroPitchSensor, {})
        assert s.native_value is None

    def test_gyro_disabled_by_default(self):
        assert YarboGyroPitchSensor._attr_entity_registry_enabled_default is False
        assert YarboGyroRollSensor._attr_entity_registry_enabled_default is False
