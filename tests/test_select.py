"""Tests for YarboConfigSelect and YarboPlanSelect.

Covers: _get_state_value, _handle_coordinator_update (cooldown + value_map),
YarboPlanSelect.options and async_select_option.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from custom_components.yarbo.select import YarboConfigSelect, YarboPlanSelect

SN = "SN001"


def _make_config_select(
    device_data=None,
    state_value_map=None,
    value_map=None,
    command_key=None,
    extra_payload=None,
    command_topic="set_state",
    current_option=None,
):
    device = MagicMock()
    device.sn = SN
    device.type_id = "T01"

    ctrl_def = MagicMock()
    ctrl_def.path = "StateMSG.working_state"
    ctrl_def.state_value_map = state_value_map
    ctrl_def.value_map = value_map
    ctrl_def.command_key = command_key
    ctrl_def.extra_payload = extra_payload
    ctrl_def.command_topic = command_topic
    ctrl_def.enabled_by_default = True
    ctrl_def.icon = None
    ctrl_def.options = []
    ctrl_def.name = "Working State"

    coord = MagicMock()
    coord.data = {SN: device_data} if device_data is not None else None
    coord._client = None

    sel = YarboConfigSelect.__new__(YarboConfigSelect)
    sel._device = device
    sel._ctrl_def = ctrl_def
    sel.coordinator = coord
    sel._command_sent_at = 0.0
    sel._attr_current_option = current_option
    sel._attr_name = ctrl_def.name
    sel.hass = MagicMock()
    return sel


def _make_plan_select(plans=None):
    device = MagicMock()
    device.sn = SN
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord.plan_data = {SN: plans or []}

    sel = YarboPlanSelect.__new__(YarboPlanSelect)
    sel._device = device
    sel.coordinator = coord
    sel._attr_current_option = None
    sel._plan_id_map = {}
    return sel


# ---------------------------------------------------------------------------
# YarboConfigSelect._get_state_value
# ---------------------------------------------------------------------------


class TestGetStateValue:
    def test_returns_field_value(self):
        sel = _make_config_select(device_data={"StateMSG": {"working_state": 1}})
        assert sel._get_state_value() == 1

    def test_no_coordinator_data_returns_none(self):
        sel = _make_config_select()
        assert sel._get_state_value() is None

    def test_missing_sn_returns_none(self):
        sel = _make_config_select(device_data={})
        assert sel._get_state_value() is None


# ---------------------------------------------------------------------------
# YarboConfigSelect._handle_coordinator_update
# ---------------------------------------------------------------------------


class TestHandleCoordinatorUpdate:
    def test_maps_raw_value_to_option(self):
        sel = _make_config_select(
            device_data={"StateMSG": {"working_state": 0}},
            state_value_map={"0": "standby", "1": "working"},
        )
        with patch.object(type(sel), "async_write_ha_state"):
            sel._handle_coordinator_update()
        assert sel._attr_current_option == "standby"

    def test_no_update_when_value_unchanged(self):
        sel = _make_config_select(
            device_data={"StateMSG": {"working_state": 1}},
            state_value_map={"1": "working"},
            current_option="working",
        )
        with patch.object(type(sel), "async_write_ha_state"):
            sel._handle_coordinator_update()
        assert sel._attr_current_option == "working"

    def test_skips_map_when_raw_is_none(self):
        sel = _make_config_select(
            device_data={},
            state_value_map={"0": "standby"},
            current_option="standby",
        )
        with patch.object(type(sel), "async_write_ha_state"):
            sel._handle_coordinator_update()
        assert sel._attr_current_option == "standby"

    def test_skips_update_during_cooldown(self):
        sel = _make_config_select(
            device_data={"StateMSG": {"working_state": 0}},
            state_value_map={"0": "standby"},
            current_option="working",
        )
        sel._command_sent_at = time.monotonic()  # within cooldown
        with patch.object(type(sel), "async_write_ha_state"):
            sel._handle_coordinator_update()
        # option should NOT change during cooldown
        assert sel._attr_current_option == "working"


# ---------------------------------------------------------------------------
# YarboPlanSelect.options
# ---------------------------------------------------------------------------


class TestPlanSelectOptions:
    def test_returns_plan_names(self):
        sel = _make_plan_select(
            plans=[
                {"id": 1, "name": "Front Lawn"},
                {"id": 2, "name": "Back Yard"},
            ]
        )
        assert sel.options == ["Front Lawn", "Back Yard"]

    def test_empty_when_no_plans(self):
        sel = _make_plan_select()
        assert sel.options == []

    def test_skips_entries_missing_name_or_id(self):
        sel = _make_plan_select(
            plans=[
                {"id": 1, "name": "Good Plan"},
                {"name": "Missing ID"},
                {"id": 3},
            ]
        )
        assert sel.options == ["Good Plan"]

    def test_builds_plan_id_map(self):
        sel = _make_plan_select(plans=[{"id": 7, "name": "Side Yard"}])
        _ = sel.options  # trigger map build
        assert sel._plan_id_map == {"Side Yard": 7}


# ---------------------------------------------------------------------------
# YarboPlanSelect.current_option
# ---------------------------------------------------------------------------


class TestPlanSelectCurrentOption:
    def _sel(self, plans, selected_id=None, attr=None, plan_feedback=None):
        sel = _make_plan_select(plans=plans)
        sel.coordinator.get_selected_plan = MagicMock(return_value=selected_id)
        sel.coordinator.plan_feedback = {SN: plan_feedback} if plan_feedback else {}
        sel._attr_current_option = attr
        return sel

    def test_resolves_name_from_plan_feedback_area_ids(self):
        plans = [{"id": 1, "name": "Front Lawn", "areaIds": [10, 20]}]
        sel = self._sel(plans, plan_feedback={"areaIds": [10, 20]})
        assert sel.current_option == "Front Lawn"

    def test_plan_feedback_takes_priority_over_selected_id(self):
        plans = [
            {"id": 1, "name": "Front Lawn", "areaIds": [10, 20]},
            {"id": 2, "name": "Back Yard", "areaIds": [30]},
        ]
        sel = self._sel(plans, selected_id=2, plan_feedback={"areaIds": [10, 20]})
        assert sel.current_option == "Front Lawn"

    def test_falls_back_to_selected_plan_id_when_no_feedback(self):
        sel = self._sel([{"id": 5, "name": "Front Lawn"}], selected_id=5)
        assert sel.current_option == "Front Lawn"

    def test_falls_back_to_attr_when_no_selected_id(self):
        sel = self._sel(
            [{"id": 5, "name": "Front Lawn"}], selected_id=None, attr="Back Yard"
        )
        assert sel.current_option == "Back Yard"

    def test_falls_back_to_attr_when_id_not_in_plan_list(self):
        sel = self._sel(
            [{"id": 5, "name": "Front Lawn"}], selected_id=99, attr="Back Yard"
        )
        assert sel.current_option == "Back Yard"

    def test_returns_none_when_no_selection_and_no_attr(self):
        sel = self._sel([], selected_id=None, attr=None)
        assert sel.current_option is None
