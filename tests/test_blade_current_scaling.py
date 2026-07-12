"""Unit tests for left/right blade current (÷100) and power (V×I) sensors.

The device encodes motor current as a fixed-point integer: 1 unit = 0.01 A.
This is a common embedded/motor-controller convention to avoid floating point
on the MCU — 50 on the wire means 0.50 A, 153 means 1.53 A.
Power sensors multiply the scaled current by live battery voltage (BatteryMSG.voltage),
which may arrive in V or mV; the >1000 guard normalises to V.
"""

from unittest.mock import MagicMock


from custom_components.yarbo.sensor import (
    YarboLeftBladeCurrentSensor,
    YarboLeftBladePowerSensor,
    YarboLeftBladeRpmSensor,
    YarboRightBladeCurrentSensor,
    YarboRightBladePowerSensor,
)

SN = "TEST_SN_BLD"


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
# YarboLeftBladeCurrentSensor
# ---------------------------------------------------------------------------


class TestYarboLeftBladeCurrentSensor:
    def test_typical_value_divided_by_100(self):
        # device reports 50 → should display 0.5 A
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {"left_blade_motor_current": 50}},
        )
        assert s.native_value == 0.5

    def test_large_value_divided_by_100(self):
        # device reports 153 → should display 1.53 A
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {"left_blade_motor_current": 153}},
        )
        assert s.native_value == 1.53

    def test_zero(self):
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {"left_blade_motor_current": 0}},
        )
        assert s.native_value == 0.0

    def test_float_raw_value(self):
        # device could send float too
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {"left_blade_motor_current": 75.0}},
        )
        assert s.native_value == 0.75

    def test_missing_msg_key_returns_none(self):
        s = _make(YarboLeftBladeCurrentSensor, {})
        assert s.native_value is None

    def test_missing_mqtt_key_returns_none(self):
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {}},
        )
        assert s.native_value is None

    def test_string_value_returns_none(self):
        s = _make(
            YarboLeftBladeCurrentSensor,
            {"mower_head_info03": {"left_blade_motor_current": "bad"}},
        )
        assert s.native_value is None

    def test_native_unit_is_amps(self):
        s = _make(YarboLeftBladeCurrentSensor, {})
        assert s.native_unit_of_measurement == "A"


# ---------------------------------------------------------------------------
# YarboRightBladeCurrentSensor
# ---------------------------------------------------------------------------


class TestYarboRightBladeCurrentSensor:
    def test_typical_value_divided_by_100(self):
        s = _make(
            YarboRightBladeCurrentSensor,
            {"mower_head_info04": {"right_blade_motor_current": 50}},
        )
        assert s.native_value == 0.5

    def test_large_value_divided_by_100(self):
        s = _make(
            YarboRightBladeCurrentSensor,
            {"mower_head_info04": {"right_blade_motor_current": 153}},
        )
        assert s.native_value == 1.53

    def test_zero(self):
        s = _make(
            YarboRightBladeCurrentSensor,
            {"mower_head_info04": {"right_blade_motor_current": 0}},
        )
        assert s.native_value == 0.0

    def test_missing_msg_key_returns_none(self):
        s = _make(YarboRightBladeCurrentSensor, {})
        assert s.native_value is None

    def test_missing_mqtt_key_returns_none(self):
        s = _make(
            YarboRightBladeCurrentSensor,
            {"mower_head_info04": {}},
        )
        assert s.native_value is None

    def test_string_value_returns_none(self):
        s = _make(
            YarboRightBladeCurrentSensor,
            {"mower_head_info04": {"right_blade_motor_current": "bad"}},
        )
        assert s.native_value is None

    def test_native_unit_is_amps(self):
        s = _make(YarboRightBladeCurrentSensor, {})
        assert s.native_unit_of_measurement == "A"


# ---------------------------------------------------------------------------
# YarboLeftBladePowerSensor
# ---------------------------------------------------------------------------


class TestYarboLeftBladePowerSensor:
    def _data(self, current_raw, voltage_raw):
        return {
            "mower_head_info03": {"left_blade_motor_current": current_raw},
            "BatteryMSG": {"voltage": voltage_raw},
        }

    def test_nominal_voltage_v(self):
        # 36 V × 0.50 A = 18.0 W
        s = _make(YarboLeftBladePowerSensor, self._data(50, 36.0))
        assert s.native_value == 18.0

    def test_full_charge_voltage_v(self):
        # 42 V × 1.53 A = 64.26 W
        s = _make(YarboLeftBladePowerSensor, self._data(153, 42.0))
        assert s.native_value == 64.26

    def test_voltage_as_millivolts(self):
        # 36000 mV → 36 V; 36 × 0.50 = 18.0 W
        s = _make(YarboLeftBladePowerSensor, self._data(50, 36000))
        assert s.native_value == 18.0

    def test_zero_current(self):
        s = _make(YarboLeftBladePowerSensor, self._data(0, 36.0))
        assert s.native_value == 0.0

    def test_missing_voltage_returns_none(self):
        s = _make(
            YarboLeftBladePowerSensor,
            {"mower_head_info03": {"left_blade_motor_current": 50}},
        )
        assert s.native_value is None

    def test_missing_current_returns_none(self):
        s = _make(YarboLeftBladePowerSensor, {"BatteryMSG": {"voltage": 36.0}})
        assert s.native_value is None

    def test_string_current_returns_none(self):
        s = _make(YarboLeftBladePowerSensor, self._data("bad", 36.0))
        assert s.native_value is None

    def test_native_unit_is_watts(self):
        s = _make(YarboLeftBladePowerSensor, {})
        assert s.native_unit_of_measurement == "W"

    def test_negative_current_gives_positive_watts(self):
        # Left blade CCW: raw -50 → |−0.50 A| × 36 V = 18.0 W
        s = _make(YarboLeftBladePowerSensor, self._data(-50, 36.0))
        assert s.native_value == 18.0


# ---------------------------------------------------------------------------
# YarboRightBladePowerSensor
# ---------------------------------------------------------------------------


class TestYarboRightBladePowerSensor:
    def _data(self, current_raw, voltage_raw):
        return {
            "mower_head_info04": {"right_blade_motor_current": current_raw},
            "BatteryMSG": {"voltage": voltage_raw},
        }

    def test_nominal_voltage_v(self):
        # 36 V × 0.50 A = 18.0 W
        s = _make(YarboRightBladePowerSensor, self._data(50, 36.0))
        assert s.native_value == 18.0

    def test_full_charge_voltage_v(self):
        # 42 V × 1.53 A = 64.26 W
        s = _make(YarboRightBladePowerSensor, self._data(153, 42.0))
        assert s.native_value == 64.26

    def test_voltage_as_millivolts(self):
        # 36000 mV → 36 V; 36 × 0.50 = 18.0 W
        s = _make(YarboRightBladePowerSensor, self._data(50, 36000))
        assert s.native_value == 18.0

    def test_zero_current(self):
        s = _make(YarboRightBladePowerSensor, self._data(0, 36.0))
        assert s.native_value == 0.0

    def test_missing_voltage_returns_none(self):
        s = _make(
            YarboRightBladePowerSensor,
            {"mower_head_info04": {"right_blade_motor_current": 50}},
        )
        assert s.native_value is None

    def test_missing_current_returns_none(self):
        s = _make(YarboRightBladePowerSensor, {"BatteryMSG": {"voltage": 36.0}})
        assert s.native_value is None

    def test_native_unit_is_watts(self):
        s = _make(YarboRightBladePowerSensor, {})
        assert s.native_unit_of_measurement == "W"


# ---------------------------------------------------------------------------
# YarboLeftBladeRpmSensor — abs value + direction attribute
# ---------------------------------------------------------------------------


class TestYarboLeftBladeRpmSensor:
    def _data(self, rpm_raw):
        return {"mower_head_info03": {"left_blade_motor_rpm": rpm_raw}}

    def test_negative_rpm_returns_abs(self):
        # Left blade CCW: raw -3000 → 3000 rpm displayed
        s = _make(YarboLeftBladeRpmSensor, self._data(-3000))
        assert s.native_value == 3000.0

    def test_positive_rpm_unchanged(self):
        s = _make(YarboLeftBladeRpmSensor, self._data(3000))
        assert s.native_value == 3000.0

    def test_zero_rpm(self):
        s = _make(YarboLeftBladeRpmSensor, self._data(0))
        assert s.native_value == 0.0

    def test_direction_ccw_when_negative(self):
        s = _make(YarboLeftBladeRpmSensor, self._data(-3000))
        assert s.extra_state_attributes.get("direction") == "CCW"

    def test_direction_cw_when_positive(self):
        s = _make(YarboLeftBladeRpmSensor, self._data(3000))
        assert s.extra_state_attributes.get("direction") == "CW"

    def test_direction_cw_when_zero(self):
        s = _make(YarboLeftBladeRpmSensor, self._data(0))
        assert s.extra_state_attributes.get("direction") == "CW"

    def test_missing_data_returns_none_and_empty_attrs(self):
        s = _make(YarboLeftBladeRpmSensor, {})
        assert s.native_value is None
        assert s.extra_state_attributes == {}

    def test_native_unit_is_rpm(self):
        s = _make(YarboLeftBladeRpmSensor, {})
        assert s.native_unit_of_measurement == "rpm"
