"""Tests for YarboConfigSensor numeric, enum, and value_map extraction.

Covers: plain field extraction, numeric coercion, value_map lookup,
_as_number edge cases, and unique_id / name wiring.
"""

from unittest.mock import MagicMock

from custom_components.yarbo.sensor import YarboConfigSensor

SN = "DEVICE_SN"


def _coord(device_data: dict | None = None):
    c = MagicMock()
    c.data = {SN: device_data} if device_data is not None else {}
    return c


def _device():
    d = MagicMock()
    d.sn = SN
    d.name = "Yarbo Y1"
    d.model = "Y1"
    return d


def _make_field_def(
    path="StateMSG.battery",
    custom_extractor=None,
    value_map=None,
    device_class=None,
    unit=None,
    icon=None,
    enabled_by_default=True,
    name="Battery",
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


def _sensor(coord, field_def):
    return YarboConfigSensor(coord, _device(), field_def)


# ---------------------------------------------------------------------------
# Plain numeric extraction
# ---------------------------------------------------------------------------


class TestNumericExtraction:
    def _make(self, raw, unit="%", device_class="battery"):
        coord = _coord({"StateMSG": {"battery": raw}})
        fd = _make_field_def(
            path="StateMSG.battery", unit=unit, device_class=device_class
        )
        return _sensor(coord, fd)

    def test_integer_passthrough(self):
        assert self._make(85).native_value == 85

    def test_float_passthrough(self):
        assert self._make(85.5).native_value == 85.5

    def test_string_number_coerced(self):
        assert self._make("85").native_value == 85

    def test_whole_float_string_coerced_to_int(self):
        assert self._make("85.0").native_value == 85

    def test_empty_string_returns_none(self):
        assert self._make("").native_value is None

    def test_non_numeric_string_returns_none(self):
        assert self._make("N/A").native_value is None

    def test_missing_field_returns_none(self):
        coord = _coord({})
        fd = _make_field_def(unit="%", device_class="battery")
        assert _sensor(coord, fd).native_value is None

    def test_no_data_returns_none(self):
        fd = _make_field_def(unit="%", device_class="battery")
        assert _sensor(_coord(), fd).native_value is None


# ---------------------------------------------------------------------------
# Non-numeric plain extraction (no unit, no measurement device_class)
# ---------------------------------------------------------------------------


class TestPlainExtraction:
    def _make(self, raw):
        coord = _coord({"StateMSG": {"firmware": raw}})
        fd = _make_field_def(
            path="StateMSG.firmware",
            unit=None,
            device_class=None,
            name="Firmware",
        )
        return _sensor(coord, fd)

    def test_string_passthrough(self):
        assert self._make("1.2.3").native_value == "1.2.3"

    def test_integer_passthrough(self):
        assert self._make(5).native_value == 5

    def test_none_returns_none(self):
        assert self._make(None).native_value is None


# ---------------------------------------------------------------------------
# value_map (enum) extraction
# ---------------------------------------------------------------------------


class TestValueMap:
    def _make(self, raw, value_map):
        coord = _coord({"StateMSG": {"working_state": raw}})
        fd = _make_field_def(
            path="StateMSG.working_state",
            value_map=value_map,
            unit=None,
            device_class=None,
            name="Working State",
        )
        return _sensor(coord, fd)

    def test_mapped_value_returned(self):
        assert self._make(0, {"0": "Idle", "1": "Mowing"}).native_value == "Idle"

    def test_second_mapped_value(self):
        assert self._make(1, {"0": "Idle", "1": "Mowing"}).native_value == "Mowing"

    def test_unmapped_positive_returns_none(self):
        assert self._make(99, {"0": "Idle"}).native_value is None

    def test_negative_falls_back_to_minus_one(self):
        assert self._make(-5, {"0": "Idle", "-1": "Error"}).native_value == "Error"

    def test_negative_no_fallback_returns_none(self):
        assert self._make(-5, {"0": "Idle"}).native_value is None

    def test_missing_data_returns_none(self):
        fd = _make_field_def(
            value_map={"0": "Idle"},
            unit=None,
            device_class=None,
        )
        assert _sensor(_coord(), fd).native_value is None


# ---------------------------------------------------------------------------
# _as_number static method directly
# ---------------------------------------------------------------------------


class TestAsNumber:
    def test_int(self):
        assert YarboConfigSensor._as_number(42) == 42

    def test_float(self):
        assert YarboConfigSensor._as_number(3.14) == 3.14

    def test_whole_float_becomes_int(self):
        assert YarboConfigSensor._as_number(3.0) == 3

    def test_string_int(self):
        assert YarboConfigSensor._as_number("42") == 42

    def test_string_float(self):
        assert YarboConfigSensor._as_number("3.14") == 3.14

    def test_empty_string_returns_none(self):
        assert YarboConfigSensor._as_number("") is None

    def test_none_returns_none(self):
        assert YarboConfigSensor._as_number(None) is None

    def test_non_numeric_string_returns_none(self):
        assert YarboConfigSensor._as_number("abc") is None


# ---------------------------------------------------------------------------
# Unique ID format — changing this breaks all existing HA entity history
# ---------------------------------------------------------------------------


class TestUniqueIdFormat:
    def test_simple_path(self):
        fd = _make_field_def(path="StateMSG.battery", name="Battery")
        assert _sensor(_coord(), fd)._attr_unique_id == f"{SN}_statemsg_battery"

    def test_nested_path_dots_become_underscores(self):
        fd = _make_field_def(path="WheelSpeedMSG.left_speed")
        assert _sensor(_coord(), fd)._attr_unique_id == f"{SN}_wheelspeedmsg_left_speed"
