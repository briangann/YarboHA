"""Unit tests for left/right wheel motor power sensors.

Wheel current is already in amps (no fixed-point scaling unlike blade motors).
Track motors reverse for turning so current can be negative; watts use abs(I).
P = V × |I|. Voltage may arrive in V or mV (>1000 guard normalises to V).
"""

from unittest.mock import MagicMock

from custom_components.yarbo.sensor import (
    YarboLeftWheelMotorPowerSensor,
    YarboRightWheelMotorPowerSensor,
)

SN = "TEST_SN_WHL"


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
# YarboLeftWheelMotorPowerSensor
# ---------------------------------------------------------------------------


class TestYarboLeftWheelMotorPowerSensor:
    def _data(self, current, voltage):
        return {
            "EletricMSG": {"lwheel_current": current},
            "BatteryMSG": {"voltage": voltage},
        }

    def test_positive_current(self):
        # 36 V × 2.0 A = 72.0 W
        s = _make(YarboLeftWheelMotorPowerSensor, self._data(2.0, 36.0))
        assert s.native_value == 72.0

    def test_negative_current_gives_positive_watts(self):
        # Reversing: -2.0 A → |2.0| × 36 V = 72.0 W
        s = _make(YarboLeftWheelMotorPowerSensor, self._data(-2.0, 36.0))
        assert s.native_value == 72.0

    def test_voltage_as_millivolts(self):
        # 36000 mV → 36 V; 36 × 2.0 = 72.0 W
        s = _make(YarboLeftWheelMotorPowerSensor, self._data(2.0, 36000))
        assert s.native_value == 72.0

    def test_zero_current(self):
        s = _make(YarboLeftWheelMotorPowerSensor, self._data(0, 36.0))
        assert s.native_value == 0.0

    def test_missing_voltage_returns_none(self):
        s = _make(
            YarboLeftWheelMotorPowerSensor, {"EletricMSG": {"lwheel_current": 2.0}}
        )
        assert s.native_value is None

    def test_missing_current_returns_none(self):
        s = _make(YarboLeftWheelMotorPowerSensor, {"BatteryMSG": {"voltage": 36.0}})
        assert s.native_value is None

    def test_string_current_returns_none(self):
        s = _make(YarboLeftWheelMotorPowerSensor, self._data("bad", 36.0))
        assert s.native_value is None

    def test_native_unit_is_watts(self):
        s = _make(YarboLeftWheelMotorPowerSensor, {})
        assert s.native_unit_of_measurement == "W"


# ---------------------------------------------------------------------------
# YarboRightWheelMotorPowerSensor
# ---------------------------------------------------------------------------


class TestYarboRightWheelMotorPowerSensor:
    def _data(self, current, voltage):
        return {
            "EletricMSG": {"rwheel_current": current},
            "BatteryMSG": {"voltage": voltage},
        }

    def test_positive_current(self):
        s = _make(YarboRightWheelMotorPowerSensor, self._data(2.0, 36.0))
        assert s.native_value == 72.0

    def test_negative_current_gives_positive_watts(self):
        s = _make(YarboRightWheelMotorPowerSensor, self._data(-2.0, 36.0))
        assert s.native_value == 72.0

    def test_voltage_as_millivolts(self):
        s = _make(YarboRightWheelMotorPowerSensor, self._data(2.0, 36000))
        assert s.native_value == 72.0

    def test_zero_current(self):
        s = _make(YarboRightWheelMotorPowerSensor, self._data(0, 36.0))
        assert s.native_value == 0.0

    def test_missing_voltage_returns_none(self):
        s = _make(
            YarboRightWheelMotorPowerSensor, {"EletricMSG": {"rwheel_current": 2.0}}
        )
        assert s.native_value is None

    def test_missing_current_returns_none(self):
        s = _make(YarboRightWheelMotorPowerSensor, {"BatteryMSG": {"voltage": 36.0}})
        assert s.native_value is None

    def test_native_unit_is_watts(self):
        s = _make(YarboRightWheelMotorPowerSensor, {})
        assert s.native_unit_of_measurement == "W"
