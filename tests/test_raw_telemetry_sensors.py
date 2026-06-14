"""Unit tests for raw telemetry sensor classes restored from v0.4.8.

These classes read directly from coordinator.data[sn] MQTT payloads.
All tests are pure-logic (no HA hass fixture needed).
"""

from unittest.mock import MagicMock

from custom_components.yarbo.sensor import (
    YarboChuteSensor,
    YarboGyroRollSensor,
    YarboGyroPitchSensor,
    YarboOdomConfidenceSensor,
    YarboOdometryLeftSensor,
    YarboOdometryRightSensor,
    YarboProximityCenterSensor,
    YarboProximityLeftSensor,
    YarboProximityRightSensor,
    YarboSpeedSensor,
)

SN = "TEST_SN_001"


def _coord(device_data: dict | None = None):
    c = MagicMock()
    c.data = {SN: device_data} if device_data is not None else {}
    return c


def _device():
    d = MagicMock()
    d.sn = SN
    d.name = "Test Robot"
    d.model = "Y900"
    return d


def _make(cls, device_data: dict | None = None):
    return cls(_coord(device_data), _device())


# ---------------------------------------------------------------------------
# YarboSpeedSensor
# ---------------------------------------------------------------------------


class TestYarboSpeedSensor:
    def test_both_wheels_present(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0.5, "right": 0.7}})
        assert s.native_value == round((0.5 + 0.7) / 2.0, 3)

    def test_zero_speed(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0, "right": 0}})
        assert s.native_value == 0.0

    def test_missing_left_returns_none(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"right": 0.5}})
        assert s.native_value is None

    def test_missing_right_returns_none(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": 0.5}})
        assert s.native_value is None

    def test_string_value_returns_none(self):
        s = _make(YarboSpeedSensor, {"WheelSpeedMSG": {"left": "fast", "right": 0.5}})
        assert s.native_value is None

    def test_no_wheel_msg_returns_none(self):
        assert _make(YarboSpeedSensor, {}).native_value is None

    def test_no_data_returns_none(self):
        assert _make(YarboSpeedSensor).native_value is None

    def test_unique_id_format(self):
        assert _make(YarboSpeedSensor).unique_id == f"{SN}_speed"


# ---------------------------------------------------------------------------
# YarboOdometryLeftSensor
# ---------------------------------------------------------------------------


class TestYarboOdometryLeftSensor:
    def test_normal_value(self):
        s = _make(YarboOdometryLeftSensor, {"WheelSpeedMSG": {"dist_left": 12.345}})
        assert s.native_value == round(12.345, 1)

    def test_integer_value(self):
        s = _make(YarboOdometryLeftSensor, {"WheelSpeedMSG": {"dist_left": 100}})
        assert s.native_value == 100.0

    def test_missing_key_returns_none(self):
        s = _make(YarboOdometryLeftSensor, {"WheelSpeedMSG": {}})
        assert s.native_value is None

    def test_no_wheel_msg_returns_none(self):
        assert _make(YarboOdometryLeftSensor, {}).native_value is None

    def test_unique_id_format(self):
        assert _make(YarboOdometryLeftSensor).unique_id == f"{SN}_odometry_left"


# ---------------------------------------------------------------------------
# YarboOdometryRightSensor
# ---------------------------------------------------------------------------


class TestYarboOdometryRightSensor:
    def test_normal_value(self):
        s = _make(YarboOdometryRightSensor, {"WheelSpeedMSG": {"dist_right": 9.87}})
        assert s.native_value == round(9.87, 1)

    def test_missing_key_returns_none(self):
        s = _make(YarboOdometryRightSensor, {"WheelSpeedMSG": {}})
        assert s.native_value is None

    def test_unique_id_format(self):
        assert _make(YarboOdometryRightSensor).unique_id == f"{SN}_odometry_right"


# ---------------------------------------------------------------------------
# YarboOdomConfidenceSensor
# ---------------------------------------------------------------------------


class TestYarboOdomConfidenceSensor:
    def test_high_confidence(self):
        s = _make(YarboOdomConfidenceSensor, {"combined_odom_confidence": 0.987})
        assert s.native_value == round(0.987, 3)

    def test_zero_confidence(self):
        s = _make(YarboOdomConfidenceSensor, {"combined_odom_confidence": 0})
        assert s.native_value == 0.0

    def test_missing_key_returns_none(self):
        assert _make(YarboOdomConfidenceSensor, {}).native_value is None

    def test_no_data_returns_none(self):
        assert _make(YarboOdomConfidenceSensor).native_value is None

    def test_unique_id_format(self):
        assert _make(YarboOdomConfidenceSensor).unique_id == f"{SN}_odom_confidence"


# ---------------------------------------------------------------------------
# YarboChuteSensor (Snow Blower head only)
# ---------------------------------------------------------------------------


class TestYarboChuteSensor:
    def test_angle_value(self):
        s = _make(YarboChuteSensor, {"RunningStatusMSG": {"chute_angle": 45.0}})
        assert s.native_value == 45.0

    def test_zero_angle(self):
        s = _make(YarboChuteSensor, {"RunningStatusMSG": {"chute_angle": 0}})
        assert s.native_value == 0.0

    def test_missing_key_returns_none(self):
        s = _make(YarboChuteSensor, {"RunningStatusMSG": {}})
        assert s.native_value is None

    def test_unique_id_format(self):
        assert _make(YarboChuteSensor).unique_id == f"{SN}_chute_angle"

    def test_head_type_required_is_snow_blower(self):
        # _HEAD_SNOW_BLOWER = (1,) — verify the class carries the gating
        assert YarboChuteSensor._head_type_required == (1,)


# ---------------------------------------------------------------------------
# YarboProximityLeftSensor — sentinel filtering
# ---------------------------------------------------------------------------


class TestYarboProximityLeftSensor:
    def test_obstacle_detected(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": 350.0}})
        assert s.native_value == 350.0

    def test_sentinel_9999_returns_none(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": 9999}})
        assert s.native_value is None

    def test_value_above_9999_returns_none(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": 10000}})
        assert s.native_value is None

    def test_value_below_9999_passes(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": 9998}})
        assert s.native_value == 9998.0

    def test_zero_distance(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": 0}})
        assert s.native_value == 0.0

    def test_missing_key_returns_none(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {}})
        assert s.native_value is None

    def test_string_value_returns_none(self):
        s = _make(YarboProximityLeftSensor, {"ultrasonic_msg": {"lf_dis": "far"}})
        assert s.native_value is None

    def test_unique_id_format(self):
        assert _make(YarboProximityLeftSensor).unique_id == f"{SN}_proximity_left"


# ---------------------------------------------------------------------------
# YarboProximityCenterSensor
# ---------------------------------------------------------------------------


class TestYarboProximityCenterSensor:
    def test_obstacle_detected(self):
        s = _make(YarboProximityCenterSensor, {"ultrasonic_msg": {"mt_dis": 500}})
        assert s.native_value == 500.0

    def test_sentinel_returns_none(self):
        s = _make(YarboProximityCenterSensor, {"ultrasonic_msg": {"mt_dis": 9999}})
        assert s.native_value is None

    def test_missing_key_returns_none(self):
        s = _make(YarboProximityCenterSensor, {"ultrasonic_msg": {}})
        assert s.native_value is None

    def test_unique_id_format(self):
        assert _make(YarboProximityCenterSensor).unique_id == f"{SN}_proximity_center"


# ---------------------------------------------------------------------------
# YarboProximityRightSensor
# ---------------------------------------------------------------------------


class TestYarboProximityRightSensor:
    def test_obstacle_detected(self):
        s = _make(YarboProximityRightSensor, {"ultrasonic_msg": {"rf_dis": 200}})
        assert s.native_value == 200.0

    def test_sentinel_returns_none(self):
        s = _make(YarboProximityRightSensor, {"ultrasonic_msg": {"rf_dis": 9999}})
        assert s.native_value is None

    def test_missing_key_returns_none(self):
        s = _make(YarboProximityRightSensor, {"ultrasonic_msg": {}})
        assert s.native_value is None

    def test_unique_id_format(self):
        assert _make(YarboProximityRightSensor).unique_id == f"{SN}_proximity_right"


# ---------------------------------------------------------------------------
# YarboGyroPitchSensor
# ---------------------------------------------------------------------------


class TestYarboGyroPitchSensor:
    def test_positive_pitch(self):
        s = _make(
            YarboGyroPitchSensor, {"RunningStatusMSG": {"head_gyro_pitch": 3.14159}}
        )
        assert s.native_value == round(3.14159, 3)

    def test_negative_pitch(self):
        s = _make(YarboGyroPitchSensor, {"RunningStatusMSG": {"head_gyro_pitch": -1.5}})
        assert s.native_value == round(-1.5, 3)

    def test_zero(self):
        s = _make(YarboGyroPitchSensor, {"RunningStatusMSG": {"head_gyro_pitch": 0}})
        assert s.native_value == 0.0

    def test_missing_key_returns_none(self):
        s = _make(YarboGyroPitchSensor, {"RunningStatusMSG": {}})
        assert s.native_value is None

    def test_disabled_by_default(self):
        assert _make(YarboGyroPitchSensor).entity_registry_enabled_default is False

    def test_unique_id_format(self):
        assert _make(YarboGyroPitchSensor).unique_id == f"{SN}_gyro_pitch"


# ---------------------------------------------------------------------------
# YarboGyroRollSensor
# ---------------------------------------------------------------------------


class TestYarboGyroRollSensor:
    def test_positive_roll(self):
        s = _make(YarboGyroRollSensor, {"RunningStatusMSG": {"head_gyro_roll": 2.718}})
        assert s.native_value == round(2.718, 3)

    def test_negative_roll(self):
        s = _make(YarboGyroRollSensor, {"RunningStatusMSG": {"head_gyro_roll": -0.5}})
        assert s.native_value == round(-0.5, 3)

    def test_missing_key_returns_none(self):
        s = _make(YarboGyroRollSensor, {"RunningStatusMSG": {}})
        assert s.native_value is None

    def test_disabled_by_default(self):
        assert _make(YarboGyroRollSensor).entity_registry_enabled_default is False

    def test_unique_id_format(self):
        assert _make(YarboGyroRollSensor).unique_id == f"{SN}_gyro_roll"
