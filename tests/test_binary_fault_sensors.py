"""Tests for fault/status binary sensors."""

from unittest.mock import MagicMock

from custom_components.yarbo_bg.binary_sensor import (
    YarboImpactBinarySensor,
    YarboLeftMotorFaultSensor,
    YarboLeftWheelFaultSensor,
    YarboPowerFaultSensor,
    YarboRadarFaultSensor,
    YarboRightMotorFaultSensor,
    YarboRightWheelFaultSensor,
)

SN = "DEVICE_SN"


def _device():
    d = MagicMock()
    d.sn = SN
    d.name = "Test"
    d.model = "Y1000"
    return d


def _make(cls, abnormal_msg=None, running_status=None):
    sensor = object.__new__(cls)
    data: dict = {}
    if abnormal_msg is not None:
        data["abnormal_msg"] = abnormal_msg
    if running_status is not None:
        data["RunningStatusMSG"] = running_status
    coord = MagicMock()
    coord.data = {SN: data}
    sensor.coordinator = coord
    sensor._device = _device()
    return sensor


# ── Impact ────────────────────────────────────────────────────────────────────


class TestYarboImpactBinarySensor:
    def test_no_impact(self):
        s = _make(YarboImpactBinarySensor, running_status={"impact_sensor": 0})
        assert s.is_on is False

    def test_impact_detected(self):
        s = _make(YarboImpactBinarySensor, running_status={"impact_sensor": 1})
        assert s.is_on is True

    def test_missing_returns_none(self):
        s = _make(YarboImpactBinarySensor)
        assert s.is_on is None

    def test_string_value_treated_as_no_fault(self):
        # Non-numeric values (e.g. corrupted payload) must not fire — bool("0") would be True
        s = _make(YarboImpactBinarySensor, running_status={"impact_sensor": "0"})
        assert s.is_on is False


# ── Motor faults ──────────────────────────────────────────────────────────────


class TestYarboMotorFaultSensors:
    def test_left_no_fault(self):
        s = _make(YarboLeftMotorFaultSensor, abnormal_msg={"left_motor_err": 0})
        assert s.is_on is False

    def test_left_fault(self):
        s = _make(YarboLeftMotorFaultSensor, abnormal_msg={"left_motor_err": 1})
        assert s.is_on is True

    def test_right_no_fault(self):
        s = _make(YarboRightMotorFaultSensor, abnormal_msg={"right_motor_err": 0})
        assert s.is_on is False

    def test_right_fault(self):
        s = _make(YarboRightMotorFaultSensor, abnormal_msg={"right_motor_err": 2})
        assert s.is_on is True

    def test_missing_returns_none(self):
        s = _make(YarboLeftMotorFaultSensor)
        assert s.is_on is None


# ── Wheel faults ──────────────────────────────────────────────────────────────


class TestYarboWheelFaultSensors:
    def test_left_no_fault(self):
        s = _make(YarboLeftWheelFaultSensor, abnormal_msg={"left_wheel_fault_state": 0})
        assert s.is_on is False

    def test_left_fault(self):
        s = _make(YarboLeftWheelFaultSensor, abnormal_msg={"left_wheel_fault_state": 1})
        assert s.is_on is True

    def test_right_no_fault(self):
        s = _make(
            YarboRightWheelFaultSensor, abnormal_msg={"right_wheel_fault_state": 0}
        )
        assert s.is_on is False

    def test_right_fault(self):
        s = _make(
            YarboRightWheelFaultSensor, abnormal_msg={"right_wheel_fault_state": 1}
        )
        assert s.is_on is True


# ── Radar fault ───────────────────────────────────────────────────────────────


class TestYarboRadarFaultSensor:
    def test_no_fault(self):
        s = _make(YarboRadarFaultSensor, abnormal_msg={"radar_state": 0})
        assert s.is_on is False

    def test_fault(self):
        s = _make(YarboRadarFaultSensor, abnormal_msg={"radar_state": 1})
        assert s.is_on is True

    def test_missing_returns_none(self):
        assert _make(YarboRadarFaultSensor).is_on is None


# ── Power fault ───────────────────────────────────────────────────────────────


class TestYarboPowerFaultSensor:
    def test_minus_one_is_not_fault(self):
        # -1 = "not applicable" / nominal — must NOT fire
        s = _make(YarboPowerFaultSensor, abnormal_msg={"power_fault": -1})
        assert s.is_on is False

    def test_zero_is_not_fault(self):
        s = _make(YarboPowerFaultSensor, abnormal_msg={"power_fault": 0})
        assert s.is_on is False

    def test_positive_is_fault(self):
        s = _make(YarboPowerFaultSensor, abnormal_msg={"power_fault": 1})
        assert s.is_on is True

    def test_missing_returns_none(self):
        assert _make(YarboPowerFaultSensor).is_on is None
