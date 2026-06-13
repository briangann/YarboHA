"""Tests for button precondition safety checks.

YarboStartPlanButton and YarboRechargeButton perform multiple device-state
checks before sending MQTT commands.  Each check raises HomeAssistantError
with a specific message.  We test every branch by constructing the button
with a mock coordinator and calling async_press() directly.

Because all checks are pure dict reads that happen *before* any hass / SDK
call, we never need a live HA instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.yarbo.button import YarboRechargeButton, YarboStartPlanButton

SN = "SN001"


def _make_button(cls, data: dict, selected_plan: int | None = 42):
    """Construct a button with a fully mocked coordinator and hass."""
    device = MagicMock()
    device.sn = SN
    device.type_id = "T01"
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord.data = {SN: data}
    coord.get_selected_plan.return_value = selected_plan
    coord.bound_device.return_value = None
    coord._client = None

    btn = cls.__new__(cls)
    btn._device = device
    btn.coordinator = coord
    btn.hass = MagicMock()
    btn.hass.states.get.return_value = None
    return btn


# ---------------------------------------------------------------------------
# YarboStartPlanButton — 7 precondition checks
# ---------------------------------------------------------------------------


class TestStartPlanChecks:
    @pytest.mark.asyncio
    async def test_offline_raises(self):
        btn = _make_button(YarboStartPlanButton, {"__online__": False})
        with pytest.raises(HomeAssistantError, match="offline"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_no_plan_selected_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {"__online__": True},
            selected_plan=None,
        )
        with pytest.raises(HomeAssistantError, match="no plan selected"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_wired_charging_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {"__online__": True, "BodyMsg": {"rechargeState": 1}},
        )
        with pytest.raises(HomeAssistantError, match="wired charging"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_wired_locked_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {"__online__": True, "BodyMsg": {"rechargeState": 3}},
        )
        with pytest.raises(HomeAssistantError, match="wired charging"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_wireless_charging_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {"__online__": True, "BatteryMSG": {"status": 2}},
        )
        with pytest.raises(HomeAssistantError, match="charging"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_weak_rtk_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {"__online__": True, "RTKMSG": {"status": 3}},
        )
        with pytest.raises(HomeAssistantError, match="RTK"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_plan_already_running_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 4},
                "StateMSG": {"on_going_planning": 2, "on_going_recharging": 0},
            },
        )
        with pytest.raises(HomeAssistantError, match="already running"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_returning_to_charge_raises(self):
        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 4},
                "StateMSG": {"on_going_planning": 0, "on_going_recharging": 2},
            },
        )
        with pytest.raises(HomeAssistantError, match="returning to charge"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        """All preconditions pass; _client is None → HomeAssistantError raised."""
        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 4},
                "StateMSG": {"on_going_planning": 0, "on_going_recharging": 0},
            },
        )
        with pytest.raises(HomeAssistantError, match="not connected"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_sdk_failure_raises_home_assistant_error(self):
        """SDK raises on mqtt_publish_command → wrapped as HomeAssistantError."""
        from unittest.mock import AsyncMock

        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 4},
                "StateMSG": {"on_going_planning": 0, "on_going_recharging": 0},
            },
        )
        btn.coordinator._client = MagicMock()
        btn.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("broker down")
        )
        with pytest.raises(HomeAssistantError, match="Failed to start plan"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_planning_status_5_not_active(self):
        """on_going_planning == 5 means plan completed/idle — raises not_connected."""
        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 4},
                "StateMSG": {"on_going_planning": 5, "on_going_recharging": 0},
            },
        )
        with pytest.raises(HomeAssistantError, match="not connected"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_recharging_status_4_not_returning(self):
        """on_going_recharging == 4 means docked/charged — raises not_connected."""
        btn = _make_button(
            YarboStartPlanButton,
            {
                "__online__": True,
                "RTKMSG": {"status": 5},
                "StateMSG": {"on_going_planning": 0, "on_going_recharging": 4},
            },
        )
        with pytest.raises(HomeAssistantError, match="not connected"):
            await btn.async_press()


# ---------------------------------------------------------------------------
# YarboRechargeButton — 4 precondition checks
# ---------------------------------------------------------------------------


class TestRechargeSafetyChecks:
    @pytest.mark.asyncio
    async def test_offline_raises(self):
        btn = _make_button(YarboRechargeButton, {"__online__": False})
        with pytest.raises(HomeAssistantError, match="offline"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_already_charging_raises(self):
        btn = _make_button(
            YarboRechargeButton,
            {"__online__": True, "BatteryMSG": {"status": 2}},
        )
        with pytest.raises(HomeAssistantError, match="already charging"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_already_returning_raises(self):
        btn = _make_button(
            YarboRechargeButton,
            {
                "__online__": True,
                "StateMSG": {"on_going_recharging": 2},
            },
        )
        with pytest.raises(HomeAssistantError, match="already returning"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_weak_rtk_raises(self):
        btn = _make_button(
            YarboRechargeButton,
            {"__online__": True, "RTKMSG": {"status": 1}},
        )
        with pytest.raises(HomeAssistantError, match="RTK"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        """All preconditions pass; _client is None → HomeAssistantError raised."""
        btn = _make_button(
            YarboRechargeButton,
            {"__online__": True, "RTKMSG": {"status": 4}},
        )
        with pytest.raises(HomeAssistantError, match="not connected"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_sdk_failure_raises_home_assistant_error(self):
        """SDK raises → wrapped as HomeAssistantError."""
        from unittest.mock import AsyncMock

        btn = _make_button(
            YarboRechargeButton,
            {"__online__": True, "RTKMSG": {"status": 4}},
        )
        btn.coordinator._client = MagicMock()
        btn.hass.async_add_executor_job = AsyncMock(side_effect=Exception("timeout"))
        with pytest.raises(HomeAssistantError, match="Failed to return to charge"):
            await btn.async_press()
