"""Tests for YarboDataUpdateCoordinator sync state methods.

Tests the logic-only methods that don't require a live HA event loop:
- set_user_standby / get_user_standby (via _should_keep_awake)
- set_selected_plan / get_selected_plan
- keep_awake_mode property
- _is_charging
- _should_keep_awake (all three policy modes)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.yarbo.const import (
    CONF_KEEP_AWAKE_MODE,
    KEEP_AWAKE_ALWAYS,
    KEEP_AWAKE_DOCKED,
    KEEP_AWAKE_OFF,
)

SN = "SN001"


def _make_coordinator(options: dict | None = None, device_data: dict | None = None):
    """Build a minimal YarboDataUpdateCoordinator with mocked HA plumbing."""
    from custom_components.yarbo.coordinator import YarboDataUpdateCoordinator

    hass = MagicMock()
    entry = MagicMock()
    entry.options = options or {}
    entry.data = {}

    # Patch Store so __init__ doesn't need a real hass loop
    with patch("custom_components.yarbo.coordinator.Store", return_value=MagicMock()):
        coord = YarboDataUpdateCoordinator.__new__(YarboDataUpdateCoordinator)
        coord.hass = hass
        coord.entry = entry
        coord.logger = MagicMock()
        coord.name = "yarbo"
        coord.update_interval = None
        coord._listeners = {}
        coord._unsub_refresh = None
        coord.data = {SN: device_data} if device_data is not None else None
        coord.devices = []
        coord._client = None
        coord._user_standby = {}
        coord._selected_plan = {}
        coord._plan_data = {}
        coord._gps_refs = {}
        coord._map_data = {}
        coord._device_msg_loaded = set()
        coord._device_msg_inflight = set()
        coord._wifi_loaded = set()
        coord._wifi_inflight = set()
        coord._standby_store = MagicMock()
        coord._map_store = MagicMock()
        coord._last_heartbeat = {}
        return coord


# ---------------------------------------------------------------------------
# Plan selection
# ---------------------------------------------------------------------------


class TestPlanSelection:
    def test_get_returns_none_before_set(self):
        coord = _make_coordinator()
        assert coord.get_selected_plan(SN) is None

    def test_set_then_get(self):
        coord = _make_coordinator()
        coord.set_selected_plan(SN, 7)
        assert coord.get_selected_plan(SN) == 7

    def test_overwrite(self):
        coord = _make_coordinator()
        coord.set_selected_plan(SN, 1)
        coord.set_selected_plan(SN, 99)
        assert coord.get_selected_plan(SN) == 99

    def test_different_devices_independent(self):
        coord = _make_coordinator()
        coord.set_selected_plan("SN_A", 1)
        coord.set_selected_plan("SN_B", 2)
        assert coord.get_selected_plan("SN_A") == 1
        assert coord.get_selected_plan("SN_B") == 2


# ---------------------------------------------------------------------------
# User standby
# ---------------------------------------------------------------------------


class TestUserStandby:
    def test_set_standby_true(self):
        coord = _make_coordinator()
        coord.set_user_standby(SN, True)
        assert coord._user_standby[SN] is True

    def test_set_standby_false(self):
        coord = _make_coordinator()
        coord.set_user_standby(SN, True)
        coord.set_user_standby(SN, False)
        assert coord._user_standby[SN] is False

    def test_standby_triggers_store_save(self):
        coord = _make_coordinator()
        coord.set_user_standby(SN, True)
        coord._standby_store.async_delay_save.assert_called_once()


# ---------------------------------------------------------------------------
# keep_awake_mode property
# ---------------------------------------------------------------------------


class TestKeepAwakeMode:
    def test_defaults_to_always(self):
        coord = _make_coordinator(options={})
        assert coord.keep_awake_mode == KEEP_AWAKE_ALWAYS

    def test_reads_option(self):
        coord = _make_coordinator(options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_OFF})
        assert coord.keep_awake_mode == KEEP_AWAKE_OFF


# ---------------------------------------------------------------------------
# _is_charging
# ---------------------------------------------------------------------------


class TestIsCharging:
    def test_status_2_is_charging(self):
        coord = _make_coordinator(device_data={"BatteryMSG": {"status": 2}})
        assert coord._is_charging(SN) is True

    def test_status_1_not_charging(self):
        coord = _make_coordinator(device_data={"BatteryMSG": {"status": 1}})
        assert coord._is_charging(SN) is False

    def test_status_0_not_charging(self):
        coord = _make_coordinator(device_data={"BatteryMSG": {"status": 0}})
        assert coord._is_charging(SN) is False

    def test_no_data_not_charging(self):
        coord = _make_coordinator()
        assert coord._is_charging(SN) is False

    def test_missing_battery_msg_not_charging(self):
        coord = _make_coordinator(device_data={})
        assert coord._is_charging(SN) is False


# ---------------------------------------------------------------------------
# _should_keep_awake
# ---------------------------------------------------------------------------


class TestShouldKeepAwake:
    def test_always_mode_keeps_awake(self):
        coord = _make_coordinator(options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_ALWAYS})
        assert coord._should_keep_awake(SN) is True

    def test_off_mode_never_keeps_awake(self):
        coord = _make_coordinator(options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_OFF})
        assert coord._should_keep_awake(SN) is False

    def test_docked_mode_keeps_awake_when_charging(self):
        coord = _make_coordinator(
            options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_DOCKED},
            device_data={"BatteryMSG": {"status": 2}},
        )
        assert coord._should_keep_awake(SN) is True

    def test_docked_mode_no_keepawake_when_not_charging(self):
        coord = _make_coordinator(
            options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_DOCKED},
            device_data={"BatteryMSG": {"status": 0}},
        )
        assert coord._should_keep_awake(SN) is False

    def test_user_standby_suppresses_all_modes(self):
        coord = _make_coordinator(options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_ALWAYS})
        coord._user_standby[SN] = True
        assert coord._should_keep_awake(SN) is False

    def test_user_standby_false_doesnt_suppress(self):
        coord = _make_coordinator(options={CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_ALWAYS})
        coord._user_standby[SN] = False
        assert coord._should_keep_awake(SN) is True
