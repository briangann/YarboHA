"""Tests for YarboConfigNumber and YarboPlanStartPercent.

Covers: _build_payload (sound_volume + key builders), _format_command_value,
native_value, available, and YarboPlanStartPercent state.
"""

from __future__ import annotations

from unittest.mock import MagicMock


from custom_components.yarbo.number import YarboConfigNumber, YarboPlanStartPercent

SN = "SN001"


def _make_number(
    builder: str = "key",
    command_key: str | None = "value",
    step=None,
    extra_payload=None,
    device_data: dict | None = None,
    native_min: float = 0,
    native_max: float = 100,
):
    device = MagicMock()
    device.sn = SN
    device.name = "Yarbo Y1"
    device.model = "Y1"

    ctrl_def = MagicMock()
    ctrl_def.command_builder = builder
    ctrl_def.command_key = command_key
    ctrl_def.step = step
    ctrl_def.extra_payload = extra_payload
    ctrl_def.native_min_value = native_min
    ctrl_def.native_max_value = native_max
    ctrl_def.native_step = step or 1
    ctrl_def.path = "StateMSG.blade_speed"
    ctrl_def.name = "Test"
    ctrl_def.unit = None
    ctrl_def.enabled_by_default = True
    ctrl_def.icon = None

    coord = MagicMock()
    coord.data = {SN: device_data} if device_data is not None else None

    num = YarboConfigNumber.__new__(YarboConfigNumber)
    num._device = device
    num._ctrl_def = ctrl_def
    num.coordinator = coord
    num._optimistic_value = 0.0
    return num


# ---------------------------------------------------------------------------
# _build_payload — sound_volume builder
# ---------------------------------------------------------------------------


class TestSoundVolumePayload:
    def test_sound_enabled(self):
        num = _make_number(
            "sound_volume", device_data={"StateMSG": {"enable_sound": 1}}
        )
        payload = num._build_payload(0.7)
        assert payload == {"enable": True, "vol": 0.7, "mode": 0}

    def test_sound_disabled(self):
        num = _make_number(
            "sound_volume", device_data={"StateMSG": {"enable_sound": 0}}
        )
        payload = num._build_payload(0.5)
        assert payload["enable"] is False

    def test_missing_enable_defaults_true(self):
        num = _make_number("sound_volume", device_data={})
        payload = num._build_payload(1.0)
        assert payload["enable"] is True

    def test_volume_rounded(self):
        num = _make_number("sound_volume", device_data={})
        payload = num._build_payload(0.333)
        assert payload["vol"] == 0.3


# ---------------------------------------------------------------------------
# _build_payload — key builder (generic)
# ---------------------------------------------------------------------------


class TestKeyPayload:
    def test_integer_value_in_payload(self):
        num = _make_number("key", command_key="blade_speed")
        payload = num._build_payload(50.0)
        assert payload == {"blade_speed": 50}

    def test_float_value_preserved(self):
        num = _make_number("key", command_key="speed", step=0.1)
        payload = num._build_payload(1.5)
        assert payload == {"speed": 1.5}

    def test_extra_payload_merged(self):
        num = _make_number("key", command_key="val", extra_payload={"type": 1})
        payload = num._build_payload(3.0)
        assert payload == {"val": 3, "type": 1}

    def test_no_command_key_empty_payload(self):
        num = _make_number("key", command_key=None)  # type: ignore[arg-type]
        payload = num._build_payload(5.0)
        assert payload == {}


# ---------------------------------------------------------------------------
# _format_command_value
# ---------------------------------------------------------------------------


class TestFormatCommandValue:
    def test_whole_float_integer_step_returns_int(self):
        num = _make_number(step=1)
        assert num._format_command_value(5.0) == 5
        assert isinstance(num._format_command_value(5.0), int)

    def test_fractional_value_returns_float(self):
        num = _make_number(step=0.1)
        assert num._format_command_value(1.5) == 1.5
        assert isinstance(num._format_command_value(1.5), float)

    def test_whole_float_with_float_step_returns_float(self):
        num = _make_number(step=0.5)
        # 4.0 is integer-valued but step is non-integer → keep float
        assert num._format_command_value(4.0) == 4.0
        assert isinstance(num._format_command_value(4.0), float)

    def test_none_step_treated_as_integer_step(self):
        num = _make_number(step=None)
        result = num._format_command_value(10.0)
        assert result == 10
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# YarboPlanStartPercent — unique_id format and range bounds
# ---------------------------------------------------------------------------


class TestPlanStartPercent:
    def test_unique_id(self):
        """Unique ID format — changing breaks HA entity history."""
        device = MagicMock()
        device.sn = SN
        ent = YarboPlanStartPercent(MagicMock(), device)
        assert ent._attr_unique_id == f"{SN}_plan_start_percent"

    def test_range(self):
        """Range bounds — automations that set 90% break if max changes."""
        device = MagicMock()
        device.sn = SN
        device.name = "Yarbo Y1"
        device.model = "Y1"
        ent = YarboPlanStartPercent(MagicMock(), device)
        assert ent._attr_native_min_value == 0
        assert ent._attr_native_max_value == 99
        assert ent._attr_native_step == 1
