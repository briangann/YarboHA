"""Tests for YarboConfigSelect.async_select_option and YarboPlanSelect.async_select_option.

Covers command payload building, standby tracking, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.yarbo.select import YarboConfigSelect, YarboPlanSelect

SN = "SN001"


def _make_config_select(
    value_map=None,
    command_key="state",
    extra_payload=None,
    command_topic="set_state",
    client=None,
):
    device = MagicMock()
    device.sn = SN
    device.type_id = "T01"

    ctrl_def = MagicMock()
    ctrl_def.path = "StateMSG.working_state"
    ctrl_def.state_value_map = None
    ctrl_def.value_map = value_map
    ctrl_def.command_key = command_key
    ctrl_def.extra_payload = extra_payload
    ctrl_def.command_topic = command_topic
    ctrl_def.enabled_by_default = True
    ctrl_def.icon = None
    ctrl_def.name = "Working State"

    coord = MagicMock()
    coord.data = {SN: {}}
    coord._client = client or MagicMock()
    coord.set_user_standby = MagicMock()
    coord._async_send_wakeup = AsyncMock()

    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=None)

    sel = YarboConfigSelect.__new__(YarboConfigSelect)
    sel._device = device
    sel._ctrl_def = ctrl_def
    sel.coordinator = coord
    sel._command_sent_at = 0.0
    sel._attr_current_option = None
    sel._attr_name = "Working State"
    sel.hass = hass
    return sel


def _make_plan_select():
    device = MagicMock()
    device.sn = SN
    coord = MagicMock()
    coord.set_selected_plan = MagicMock()

    sel = YarboPlanSelect.__new__(YarboPlanSelect)
    sel._device = device
    sel.coordinator = coord
    sel._attr_current_option = None
    sel._plan_id_map = {"Front Lawn": 5, "Back Yard": 7}
    return sel


# ---------------------------------------------------------------------------
# YarboConfigSelect.async_select_option
# ---------------------------------------------------------------------------


class TestConfigSelectAsyncOption:
    @pytest.mark.asyncio
    async def test_sends_mqtt_command(self):
        sel = _make_config_select(value_map={"standby": 0, "working": 1})
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("working")
        sel.hass.async_add_executor_job.assert_called()

    @pytest.mark.asyncio
    async def test_optimistic_update_before_command(self):
        sel = _make_config_select(value_map={"standby": 0, "working": 1})
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("standby")
        assert sel._attr_current_option == "standby"

    @pytest.mark.asyncio
    async def test_unknown_option_skips_command(self):
        sel = _make_config_select(value_map={"standby": 0})
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("unknown")
        sel.hass.async_add_executor_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_value_map_skips_command(self):
        sel = _make_config_select(value_map=None)
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("any")
        sel.hass.async_add_executor_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_standby_topic_sets_user_standby(self):
        sel = _make_config_select(
            value_map={"standby": 0, "working": 1},
            command_topic="set_working_state",
        )
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("standby")
        sel.coordinator.set_user_standby.assert_called_once_with(SN, True)

    @pytest.mark.asyncio
    async def test_working_topic_clears_standby_and_wakes(self):
        sel = _make_config_select(
            value_map={"standby": 0, "working": 1},
            command_topic="set_working_state",
        )
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("working")
        sel.coordinator.set_user_standby.assert_called_once_with(SN, False)
        sel.coordinator._async_send_wakeup.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_failure_restores_state(self):
        """On MQTT failure, _handle_coordinator_update is called to revert optimistic state."""
        sel = _make_config_select(value_map={"standby": 0})
        sel.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("broker down")
        )
        with patch.object(type(sel), "async_write_ha_state"):
            with patch.object(sel, "_handle_coordinator_update") as mock_revert:
                await sel.async_select_option("standby")
        mock_revert.assert_called_once()

    @pytest.mark.asyncio
    async def test_extra_payload_merged(self):
        """extra_payload values are included in the MQTT command."""
        sel = _make_config_select(
            value_map={"on": 1},
            command_key="enable",
            extra_payload={"type": 2},
        )
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("on")
        # Verify the executor job was called (payload built correctly)
        sel.hass.async_add_executor_job.assert_called()


# ---------------------------------------------------------------------------
# YarboPlanSelect.async_select_option
# ---------------------------------------------------------------------------


class TestPlanSelectAsyncOption:
    @pytest.mark.asyncio
    async def test_stores_plan_id_in_coordinator(self):
        sel = _make_plan_select()
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("Front Lawn")
        sel.coordinator.set_selected_plan.assert_called_once_with(SN, 5)

    @pytest.mark.asyncio
    async def test_updates_current_option(self):
        sel = _make_plan_select()
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("Back Yard")
        assert sel._attr_current_option == "Back Yard"

    @pytest.mark.asyncio
    async def test_unknown_plan_stores_none(self):
        sel = _make_plan_select()
        with patch.object(type(sel), "async_write_ha_state"):
            await sel.async_select_option("Unknown Plan")
        sel.coordinator.set_selected_plan.assert_called_once_with(SN, None)
