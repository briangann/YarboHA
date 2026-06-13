"""Tests for YarboConfigSwitch._build_payload.

All seven command_builder variants are pure dict construction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.yarbo.switch import YarboConfigSwitch

SN = "SN001"


def _make_switch(
    builder: str,
    path: str = "StateMSG.state",
    command_topic: str = "set_state",
    volume_in_data: float | None = None,
):
    device = MagicMock()
    device.sn = SN

    ctrl_def = MagicMock()
    ctrl_def.path = path
    ctrl_def.command_builder = builder
    ctrl_def.command_topic = command_topic
    ctrl_def.enabled_by_default = True
    ctrl_def.icon = None

    coord = MagicMock()
    if volume_in_data is not None:
        coord.data = {SN: {"StateMSG": {"volume": volume_in_data}}}
    else:
        coord.data = {SN: {}}

    sw = YarboConfigSwitch.__new__(YarboConfigSwitch)
    sw._device = device
    sw._ctrl_def = ctrl_def
    sw.coordinator = coord
    sw._command_sent_at = 0.0
    sw._follow_keepalive_unsub = None
    sw._attr_is_on = None
    return sw


class TestSoundSwitch:
    def test_turn_on_with_volume(self):
        sw = _make_switch("sound_switch", volume_in_data=0.7)
        payload = sw._build_payload(True)
        assert payload == {"enable": True, "vol": 0.7, "mode": 0}

    def test_turn_off(self):
        sw = _make_switch("sound_switch", volume_in_data=0.5)
        payload = sw._build_payload(False)
        assert payload["enable"] is False
        assert payload["vol"] == 0.5

    def test_defaults_to_1_when_volume_missing(self):
        sw = _make_switch("sound_switch")
        payload = sw._build_payload(True)
        assert payload["vol"] == 1.0


class TestLightSwitch:
    def test_turn_on(self):
        sw = _make_switch("light_switch")
        assert sw._build_payload(True) == {"led_head": 1}

    def test_turn_off(self):
        sw = _make_switch("light_switch")
        assert sw._build_payload(False) == {"led_head": 0}


class TestPersonDetectionSwitch:
    def test_turn_on(self):
        sw = _make_switch("person_detection_switch")
        assert sw._build_payload(True) == {"state": 1}

    def test_turn_off(self):
        sw = _make_switch("person_detection_switch")
        assert sw._build_payload(False) == {"state": 0}


class TestStateIntSwitch:
    def test_turn_on(self):
        sw = _make_switch("state_int_switch")
        assert sw._build_payload(True) == {"state": 1}

    def test_turn_off(self):
        sw = _make_switch("state_int_switch")
        assert sw._build_payload(False) == {"state": 0}


class TestStateBoolSwitch:
    def test_turn_on(self):
        sw = _make_switch("state_bool_switch")
        assert sw._build_payload(True) == {"state": True}

    def test_turn_off(self):
        sw = _make_switch("state_bool_switch")
        assert sw._build_payload(False) == {"state": False}


class TestGeoFenceSwitch:
    def test_turn_on(self):
        sw = _make_switch("geo_fence_switch")
        assert sw._build_payload(True) == {"id": 1, "enable_elec_fence": True}

    def test_turn_off(self):
        sw = _make_switch("geo_fence_switch")
        assert sw._build_payload(False) == {"id": 1, "enable_elec_fence": False}


class TestIgnoreObstaclesSwitch:
    def test_turn_on(self):
        sw = _make_switch("ignore_obstacles_switch")
        assert sw._build_payload(True) == {"switch": 1}

    def test_turn_off(self):
        sw = _make_switch("ignore_obstacles_switch")
        assert sw._build_payload(False) == {"switch": 0}


class TestUnknownBuilder:
    def test_raises_for_unknown_builder(self):
        sw = _make_switch("unknown_builder")
        with pytest.raises(HomeAssistantError, match="Unsupported"):
            sw._build_payload(True)
