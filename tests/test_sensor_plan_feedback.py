"""Tests for YarboConfigSensor custom_extractor logic.

Covers: planning_status, recharging_status, battery_capacity,
volume_scale, rtk_signal, charging_power, and network_priority.
"""

from unittest.mock import MagicMock

from custom_components.yarbo.sensor import (
    YarboConfigSensor,
    YarboLeftWheelCurrentSensor,
    YarboLeftWheelMotorPowerSensor,
    YarboRightWheelCurrentSensor,
    YarboRightWheelMotorPowerSensor,
    YarboWirelessChargeCurrentSensor,
    YarboWirelessChargeVoltageSensor,
)


def _make_coordinator(sn="SN001", data=None):
    coord = MagicMock()
    coord.data = {sn: data} if data is not None else {}
    return coord


def _make_device(sn="SN001"):
    d = MagicMock()
    d.sn = sn
    d.name = "Yarbo Y1"
    d.model = "Y1"
    return d


def _make_field_def(
    path="StateMSG.planning_status",
    custom_extractor=None,
    value_map=None,
    device_class=None,
    unit=None,
    icon=None,
    enabled_by_default=True,
    name="Test Sensor",
):
    fd = MagicMock()
    fd.path = path
    fd.custom_extractor = custom_extractor
    fd.value_map = value_map
    fd.device_class = device_class
    fd.unit = unit
    fd.icon = icon
    fd.enabled_by_default = enabled_by_default
    fd.name = name
    return fd


def _sensor(coord, field_def, sn="SN001"):
    return YarboConfigSensor(coord, _make_device(sn), field_def)


# ---------------------------------------------------------------------------
# planning_status
# ---------------------------------------------------------------------------


class TestPlanningStatus:
    def _make(self, code):
        coord = _make_coordinator(data={"StateMSG": {"on_going_planning": code}})
        fd = _make_field_def(
            path="StateMSG.on_going_planning",
            custom_extractor="planning_status",
        )
        return _sensor(coord, fd)

    def test_code_1_mower_head_shows_mowing(self):
        # head_type 3 = Mower → "Mowing"
        coord = _make_coordinator(
            data={"StateMSG": {"on_going_planning": 1}, "HeadMsg": {"head_type": 3}}
        )
        fd = _make_field_def(
            path="StateMSG.on_going_planning", custom_extractor="planning_status"
        )
        assert _sensor(coord, fd).native_value == "Mowing"

    def test_code_1_snow_blower_head_shows_blowing_snow(self):
        coord = _make_coordinator(
            data={"StateMSG": {"on_going_planning": 1}, "HeadMsg": {"head_type": 1}}
        )
        fd = _make_field_def(
            path="StateMSG.on_going_planning", custom_extractor="planning_status"
        )
        assert _sensor(coord, fd).native_value == "Blowing Snow"

    def test_code_1_no_head_data_defaults_mowing(self):
        s = self._make(1)
        assert s.native_value == "Mowing"

    def test_negative_unmapped_returns_error(self):
        # -5 is not in PLANNING_STATUS_MAP → falls back to generic "Error"
        s = self._make(-5)
        assert s.native_value == "Error"

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(custom_extractor="planning_status")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# recharging_status
# ---------------------------------------------------------------------------


class TestRechargingStatus:
    def _make(self, code):
        coord = _make_coordinator(data={"StateMSG": {"on_going_recharging": code}})
        fd = _make_field_def(
            path="StateMSG.on_going_recharging",
            custom_extractor="recharging_status",
        )
        return _sensor(coord, fd)

    def test_code_0_not_started(self):
        s = self._make(0)
        assert s.native_value == "Not Started"

    def test_negative_code_returns_full_message(self):
        s = self._make(-3)
        assert s.native_value == "Error: Direction Uninitialized"

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(custom_extractor="recharging_status")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# battery_capacity — rescaling above 90
# ---------------------------------------------------------------------------


class TestBatteryCapacity:
    def _make(self, raw):
        coord = _make_coordinator(data={"BatteryMSG": {"capacity": raw}})
        fd = _make_field_def(
            path="BatteryMSG.capacity",
            custom_extractor="battery_capacity",
        )
        return _sensor(coord, fd)

    def test_below_90_passthrough(self):
        assert self._make(80).native_value == 80

    def test_exactly_90_passthrough(self):
        assert self._make(90).native_value == 90

    def test_95_maps_to_100(self):
        assert self._make(95).native_value == 100

    def test_96_clips_to_100(self):
        assert self._make(96).native_value == 100

    def test_91_rescaled(self):
        # 90 + (91-90)*2 = 92
        assert self._make(91).native_value == 92

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(custom_extractor="battery_capacity")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# volume_scale — 0.0–1.0 raw → 0–100
# ---------------------------------------------------------------------------


class TestVolumeScale:
    def _make(self, raw):
        coord = _make_coordinator(data={"SoundMSG": {"volume": raw}})
        fd = _make_field_def(
            path="SoundMSG.volume",
            custom_extractor="volume_scale",
        )
        return _sensor(coord, fd)

    def test_half_volume(self):
        assert self._make(0.5).native_value == 50

    def test_full_volume(self):
        assert self._make(1.0).native_value == 100

    def test_zero(self):
        assert self._make(0.0).native_value == 0

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(custom_extractor="volume_scale")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# rtk_signal — 4=Strong, 5=Medium, else=Weak
# ---------------------------------------------------------------------------


class TestRtkSignal:
    def _make(self, raw):
        coord = _make_coordinator(data={"GpsMSG": {"rtk_status": raw}})
        fd = _make_field_def(
            path="GpsMSG.rtk_status",
            custom_extractor="rtk_signal",
        )
        return _sensor(coord, fd)

    def test_4_is_strong(self):
        assert self._make(4).native_value == "Strong"

    def test_5_is_medium(self):
        assert self._make(5).native_value == "Medium"

    def test_other_is_weak(self):
        assert self._make(3).native_value == "Weak"

    def test_no_data_returns_none(self):
        # _get_device_data returns None → _extract_custom returns None early
        coord = _make_coordinator()
        fd = _make_field_def(custom_extractor="rtk_signal")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# charging_power — voltage * current (with mV/mA auto-scaling)
# ---------------------------------------------------------------------------


class TestChargingPower:
    def _make(self, voltage, current):
        coord = _make_coordinator(
            data={"BatteryMSG": {"voltage": voltage, "current": current}}
        )
        fd = _make_field_def(
            path="BatteryMSG.voltage",
            custom_extractor="charging_power",
        )
        return _sensor(coord, fd)

    def test_normal_values(self):
        # 12V * 2A = 24W
        assert self._make(12, 2).native_value == 24.0

    def test_millivolt_autoscale(self):
        # 12000 mV → 12 V, 2000 mA → 2 A → 24W
        assert self._make(12000, 2000).native_value == 24.0

    def test_slow_charge_threshold_kept(self):
        # Around the observed slow-charge range.
        assert self._make(12, 8).native_value == 96.0

    def test_fast_charge_threshold_kept(self):
        # Around the observed fast-charge range.
        assert self._make(12, 50).native_value == 600.0

    def test_over_limit_positive_returns_none(self):
        assert self._make(12, 67).native_value is None

    def test_over_limit_negative_returns_none(self):
        assert self._make(12, -67).native_value is None

    def test_missing_voltage_returns_none(self):
        coord = _make_coordinator(data={"BatteryMSG": {"current": 2}})
        fd = _make_field_def(custom_extractor="charging_power")
        assert _sensor(coord, fd).native_value is None

    def test_missing_current_returns_none(self):
        coord = _make_coordinator(data={"BatteryMSG": {"voltage": 12}})
        fd = _make_field_def(custom_extractor="charging_power")
        assert _sensor(coord, fd).native_value is None


# ---------------------------------------------------------------------------
# wireless_recharge — raw fixed-point normalization
# ---------------------------------------------------------------------------


class TestWirelessRecharge:
    def test_voltage_normalizes_millivolts(self):
        coord = _make_coordinator(data={"wireless_recharge": {"output_voltage": 4186}})
        sensor = YarboWirelessChargeVoltageSensor(coord, _make_device())
        assert sensor.native_value == 4.186

    def test_current_kept_as_is_for_small_values(self):
        coord = _make_coordinator(data={"wireless_recharge": {"output_current": 51}})
        sensor = YarboWirelessChargeCurrentSensor(coord, _make_device())
        assert sensor.native_value == 51.0


# ---------------------------------------------------------------------------
# idle wheel normalization
# ---------------------------------------------------------------------------


class TestIdleWheelNormalization:
    def _make(self, cls, current):
        coord = _make_coordinator(
            data={
                "Speed": 0,
                "StateMSG": {"activity": "Not Started"},
                "BatteryMSG": {"voltage": 41700},
                "EletricMSG": {"lwheel_current": current, "rwheel_current": current},
            }
        )
        return cls(coord, _make_device())

    def test_left_wheel_current_zeros_when_idle(self):
        assert self._make(YarboLeftWheelCurrentSensor, 0.032).native_value == 0.0

    def test_right_wheel_current_zeros_when_idle(self):
        assert self._make(YarboRightWheelCurrentSensor, 0.024).native_value == 0.0

    def test_left_wheel_power_zeros_when_idle(self):
        assert self._make(YarboLeftWheelMotorPowerSensor, 0.032).native_value == 0.0

    def test_right_wheel_power_zeros_when_idle(self):
        assert self._make(YarboRightWheelMotorPowerSensor, 0.024).native_value == 0.0
