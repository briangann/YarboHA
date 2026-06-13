"""Tests for YarboConfigSwitch async turn on/off and _dispatch_typed.

Covers: async_turn_on, async_turn_off, _async_send_command fallback path,
_dispatch_typed for all 7 builders, and follow keepalive lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.yarbo.switch import YarboConfigSwitch

SN = "SN001"


def _make_switch(
    builder: str = "state_int_switch",
    command_topic: str = "set_state",
    client=None,
    device_data=None,
):
    device = MagicMock()
    device.sn = SN
    device.type_id = "T01"

    ctrl_def = MagicMock()
    ctrl_def.command_builder = builder
    ctrl_def.command_topic = command_topic
    ctrl_def.command_key = "state"
    ctrl_def.extra_payload = None
    ctrl_def.path = "StateMSG.state"
    ctrl_def.name = "Test Switch"
    ctrl_def.enabled_by_default = True
    ctrl_def.icon = None

    coord = MagicMock()
    coord.data = {SN: device_data or {}}
    coord._client = client or MagicMock()
    coord.bound_device.return_value = None  # force raw fallback by default

    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=None)

    sw = YarboConfigSwitch.__new__(YarboConfigSwitch)
    sw._device = device
    sw._ctrl_def = ctrl_def
    sw.coordinator = coord
    sw._command_sent_at = 0.0
    sw._attr_is_on = None
    sw._follow_keepalive_unsub = None
    sw.hass = hass
    return sw


# ---------------------------------------------------------------------------
# async_turn_on / async_turn_off
# ---------------------------------------------------------------------------


class TestTurnOnOff:
    @pytest.mark.asyncio
    async def test_turn_on_sets_optimistic_state(self):
        sw = _make_switch()
        with patch.object(type(sw), "async_write_ha_state"):
            await sw.async_turn_on()
        assert sw._attr_is_on is True

    @pytest.mark.asyncio
    async def test_turn_off_clears_state(self):
        sw = _make_switch()
        sw._attr_is_on = True
        with patch.object(type(sw), "async_write_ha_state"):
            await sw.async_turn_off()
        assert sw._attr_is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_sends_command(self):
        sw = _make_switch()
        with patch.object(type(sw), "async_write_ha_state"):
            await sw.async_turn_on()
        sw.hass.async_add_executor_job.assert_called()

    @pytest.mark.asyncio
    async def test_turn_off_sends_command(self):
        sw = _make_switch()
        with patch.object(type(sw), "async_write_ha_state"):
            await sw.async_turn_off()
        sw.hass.async_add_executor_job.assert_called()

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        sw = _make_switch()
        sw.coordinator._client = None
        with patch.object(type(sw), "async_write_ha_state"):
            with pytest.raises(HomeAssistantError, match="not connected"):
                await sw.async_turn_on()

    @pytest.mark.asyncio
    async def test_command_failure_reverts_state(self):
        sw = _make_switch()
        sw.hass.async_add_executor_job = AsyncMock(side_effect=Exception("broker"))
        with patch.object(type(sw), "async_write_ha_state"):
            with patch.object(sw, "_handle_coordinator_update") as mock_revert:
                with pytest.raises(HomeAssistantError):
                    await sw.async_turn_on()
        mock_revert.assert_called_once()


# ---------------------------------------------------------------------------
# _dispatch_typed — typed SDK routing
# ---------------------------------------------------------------------------


class TestDispatchTyped:
    @pytest.mark.asyncio
    async def test_sound_switch_dispatches(self):
        sw = _make_switch("sound_switch")
        sw.coordinator.data = {SN: {"StateMSG": {"volume": 0.5}}}
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is True
        sw.hass.async_add_executor_job.assert_called()

    @pytest.mark.asyncio
    async def test_light_switch_dispatches(self):
        sw = _make_switch("light_switch")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is True

    @pytest.mark.asyncio
    async def test_person_detection_dispatches(self):
        sw = _make_switch("person_detection_switch")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, False)
        assert result is True

    @pytest.mark.asyncio
    async def test_follow_mode_state_int_dispatches(self):
        sw = _make_switch("state_int_switch", command_topic="set_follow_state")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is True

    @pytest.mark.asyncio
    async def test_state_int_other_topic_does_not_dispatch(self):
        sw = _make_switch("state_int_switch", command_topic="other")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is False

    @pytest.mark.asyncio
    async def test_child_lock_bool_dispatches(self):
        sw = _make_switch("state_bool_switch", command_topic="set_child_lock")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is True

    @pytest.mark.asyncio
    async def test_geo_fence_dispatches(self):
        sw = _make_switch("geo_fence_switch")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is True

    @pytest.mark.asyncio
    async def test_ignore_obstacles_dispatches(self):
        sw = _make_switch("ignore_obstacles_switch")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, False)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_builder_returns_false(self):
        sw = _make_switch("unknown_builder")
        bound = MagicMock()
        result = await sw._dispatch_typed(bound, True)
        assert result is False

    @pytest.mark.asyncio
    async def test_bound_device_path_used_when_available(self):
        """When bound_device returns a bound object, typed dispatch is used."""
        bound = MagicMock()
        sw = _make_switch("sound_switch")
        sw.coordinator.bound_device.return_value = bound
        sw.coordinator.data = {SN: {"StateMSG": {"volume": 0.7}}}
        with patch.object(type(sw), "async_write_ha_state"):
            await sw.async_turn_on()
        # async_add_executor_job called for sound dispatch via bound.core.set_sound_param
        sw.hass.async_add_executor_job.assert_called()


# ---------------------------------------------------------------------------
# _async_follow_keepalive
# ---------------------------------------------------------------------------


class TestFollowKeepalive:
    @pytest.mark.asyncio
    async def test_keepalive_resends_when_on(self):
        sw = _make_switch()
        sw._attr_is_on = True
        with patch.object(type(sw), "async_write_ha_state"):
            await sw._async_follow_keepalive(None)
        sw.hass.async_add_executor_job.assert_called()

    @pytest.mark.asyncio
    async def test_keepalive_stops_when_off(self):
        sw = _make_switch()
        sw._attr_is_on = False
        stop_called = []
        sw._stop_follow_keepalive = lambda: stop_called.append(True)
        await sw._async_follow_keepalive(None)
        assert stop_called  # stop was called, no command sent
