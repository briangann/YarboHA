"""Tests for YarboConfigBinarySensor and YarboOnlineBinarySensor.

Tests the is_on logic for every custom_extractor variant and value_map
resolution without requiring a live HA instance.
"""

from unittest.mock import MagicMock


from custom_components.yarbo.binary_sensor import (
    YarboConfigBinarySensor,
    YarboOnlineBinarySensor,
)


def _make_coordinator(sn="SN001", data=None):
    coord = MagicMock()
    coord.data = {sn: data} if data is not None else {}
    return coord


def _make_device(sn="SN001"):
    device = MagicMock()
    device.sn = sn
    device.name = "Yarbo Y1"
    device.model = "Y1"
    return device


def _make_field_def(
    path="FaultMSG.impact",
    custom_extractor=None,
    value_map=None,
    device_class=None,
    icon=None,
    enabled_by_default=True,
    name="Impact",
):
    fd = MagicMock()
    fd.path = path
    fd.custom_extractor = custom_extractor
    fd.value_map = value_map
    fd.device_class = device_class
    fd.icon = icon
    fd.enabled_by_default = enabled_by_default
    fd.name = name
    return fd


def _make_sensor(coordinator=None, sn="SN001", field_def=None):
    if coordinator is None:
        coordinator = _make_coordinator(sn)
    if field_def is None:
        field_def = _make_field_def()
    device = _make_device(sn)
    return YarboConfigBinarySensor(coordinator, device, field_def)


# ---------------------------------------------------------------------------
# YarboOnlineBinarySensor
# ---------------------------------------------------------------------------


class TestYarboOnlineBinarySensor:
    def test_online_true(self):
        coord = _make_coordinator(data={"__online__": True})
        sensor = YarboOnlineBinarySensor(coord, _make_device())
        assert sensor.is_on is True

    def test_online_false(self):
        coord = _make_coordinator(data={"__online__": False})
        sensor = YarboOnlineBinarySensor(coord, _make_device())
        assert sensor.is_on is False

    def test_no_data_returns_none(self):
        coord = _make_coordinator()
        sensor = YarboOnlineBinarySensor(coord, _make_device())
        assert sensor.is_on is None


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — charging_threshold
# ---------------------------------------------------------------------------


class TestChargingThreshold:
    def _sensor(self, raw):
        coord = _make_coordinator(data={"BatteryMSG": {"status": raw}})
        fd = _make_field_def(
            path="BatteryMSG.status", custom_extractor="charging_threshold"
        )
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_status_above_1_is_charging(self):
        assert self._sensor(2).is_on is True

    def test_status_1_not_charging(self):
        assert self._sensor(1).is_on is False

    def test_status_0_not_charging(self):
        assert self._sensor(0).is_on is False

    def test_string_value_returns_none(self):
        assert self._sensor("charging").is_on is None

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(
            path="BatteryMSG.status", custom_extractor="charging_threshold"
        )
        assert _make_sensor(coordinator=coord, field_def=fd).is_on is None


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — positive_threshold
# ---------------------------------------------------------------------------


class TestPositiveThreshold:
    def _sensor(self, raw):
        coord = _make_coordinator(data={"LedInfoMSG": {"led_head": raw}})
        fd = _make_field_def(
            path="LedInfoMSG.led_head", custom_extractor="positive_threshold"
        )
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_255_is_on(self):
        assert self._sensor(255).is_on is True

    def test_0_is_off(self):
        assert self._sensor(0).is_on is False

    def test_negative_is_off(self):
        assert self._sensor(-1).is_on is False

    def test_string_returns_none(self):
        assert self._sensor("on").is_on is None


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — nonzero_threshold
# ---------------------------------------------------------------------------


class TestNonzeroThreshold:
    def _sensor(self, raw):
        coord = _make_coordinator(data={"FaultMSG": {"impact": raw}})
        fd = _make_field_def(
            path="FaultMSG.impact", custom_extractor="nonzero_threshold"
        )
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_nonzero_is_active(self):
        assert self._sensor(1).is_on is True

    def test_zero_is_normal(self):
        assert self._sensor(0).is_on is False

    def test_negative_nonzero_is_active(self):
        assert self._sensor(-1).is_on is True

    def test_string_returns_none(self):
        assert self._sensor("fault").is_on is None

    def test_missing_returns_none(self):
        coord = _make_coordinator()
        fd = _make_field_def(
            path="FaultMSG.impact", custom_extractor="nonzero_threshold"
        )
        assert _make_sensor(coordinator=coord, field_def=fd).is_on is None


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — planning_problem
# ---------------------------------------------------------------------------


class TestPlanningProblem:
    def _sensor(self, raw):
        coord = _make_coordinator(data={"StateMSG": {"planning_status": raw}})
        fd = _make_field_def(
            path="StateMSG.planning_status", custom_extractor="planning_problem"
        )
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_negative_is_problem(self):
        assert self._sensor(-1).is_on is True

    def test_zero_is_not_problem(self):
        assert self._sensor(0).is_on is False

    def test_positive_is_not_problem(self):
        assert self._sensor(5).is_on is False

    def test_bad_type_returns_none(self):
        assert self._sensor("bad").is_on is None


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — value_map
# ---------------------------------------------------------------------------


class TestValueMap:
    def _sensor(self, raw, value_map):
        coord = _make_coordinator(data={"StateMSG": {"some_flag": raw}})
        fd = _make_field_def(path="StateMSG.some_flag", value_map=value_map)
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_true_string_maps_to_on(self):
        assert self._sensor(1, {"1": "true"}).is_on is True

    def test_false_string_maps_to_off(self):
        assert self._sensor(0, {"0": "false"}).is_on is False

    def test_unmapped_value_returns_none(self):
        assert self._sensor(99, {"1": "true"}).is_on is None

    def test_on_literal_maps_to_on(self):
        assert self._sensor(1, {"1": "on"}).is_on is True


# ---------------------------------------------------------------------------
# YarboConfigBinarySensor — raw bool fallback (no extractor, no value_map)
# ---------------------------------------------------------------------------


class TestRawBool:
    def _sensor(self, raw):
        coord = _make_coordinator(data={"FaultMSG": {"impact": raw}})
        fd = _make_field_def(path="FaultMSG.impact")
        return _make_sensor(coordinator=coord, field_def=fd)

    def test_true_int(self):
        assert self._sensor(1).is_on is True

    def test_false_int(self):
        assert self._sensor(0).is_on is False

    def test_none_raw(self):
        assert self._sensor(None).is_on is None
