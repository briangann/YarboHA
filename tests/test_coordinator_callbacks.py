"""Tests for YarboDataUpdateCoordinator MQTT callbacks and heartbeat logic.

Covers: _on_device_status, _on_heart_beat, _async_check_heartbeats,
_deep_merge, bound_device, _persist_maps, _async_restore_maps.

These are pure logic methods that only need a minimal coordinator instance;
no live MQTT, SDK, or HA event loop is required.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.yarbo.coordinator import YarboDataUpdateCoordinator, _deep_merge

SN = "SN001"


def _make_coordinator(device_data=None, devices=None):
    """Minimal coordinator bypassing async_setup entirely."""

    coord = YarboDataUpdateCoordinator.__new__(YarboDataUpdateCoordinator)
    coord.hass = MagicMock()
    coord.hass.loop = MagicMock()
    coord.entry = MagicMock()
    coord.entry.options = {}
    coord.logger = MagicMock()
    coord.name = "yarbo"
    coord.update_interval = None
    coord._listeners = {}
    coord._unsub_refresh = None
    coord.data = {SN: device_data} if device_data is not None else None
    coord.devices = devices or []
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
# _deep_merge (standalone function)
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_new_key_added(self):
        dst = {"a": 1}
        changed = _deep_merge(dst, {"b": 2})
        assert dst == {"a": 1, "b": 2}
        assert changed is True

    def test_unchanged_returns_false(self):
        dst = {"a": 1}
        changed = _deep_merge(dst, {"a": 1})
        assert changed is False

    def test_value_updated(self):
        dst = {"a": 1}
        changed = _deep_merge(dst, {"a": 2})
        assert dst["a"] == 2
        assert changed is True

    def test_nested_dict_merged(self):
        dst = {"StateMSG": {"battery": 80, "working_state": 0}}
        changed = _deep_merge(dst, {"StateMSG": {"battery": 85}})
        assert dst == {"StateMSG": {"battery": 85, "working_state": 0}}
        assert changed is True

    def test_heartbeat_key_not_overwritten_by_device_status(self):
        """__online__ and HeartBeatMSG must not be overwritten by status pushes."""
        dst = {"__online__": True, "HeartBeatMSG": {"seq": 1}, "BatteryMSG": {}}
        _deep_merge(dst, {"__online__": False, "HeartBeatMSG": {"seq": 2}})
        assert dst["__online__"] is True
        assert dst["HeartBeatMSG"] == {"seq": 1}

    def test_empty_dict_source_unchanged(self):
        dst = {"a": 1}
        changed = _deep_merge(dst, {})
        assert changed is False
        assert dst == {"a": 1}


# ---------------------------------------------------------------------------
# _on_device_status
# ---------------------------------------------------------------------------


class TestOnDeviceStatus:
    def test_creates_sn_entry_from_topic(self):
        coord = _make_coordinator()
        coord._on_device_status("yarbo/SN001/device", {"StateMSG": {"battery": 80}})
        assert coord.data is not None
        assert "SN001" in coord.data
        assert coord.data["SN001"]["StateMSG"]["battery"] == 80

    def test_deep_merges_into_existing_data(self):
        coord = _make_coordinator(device_data={"StateMSG": {"battery": 80, "state": 0}})
        coord._on_device_status("yarbo/SN001/device", {"StateMSG": {"battery": 85}})
        assert coord.data[SN]["StateMSG"]["battery"] == 85
        assert coord.data[SN]["StateMSG"]["state"] == 0

    def test_triggers_state_update_on_change(self):
        coord = _make_coordinator()
        coord._on_device_status("yarbo/SN001/device", {"BatteryMSG": {"capacity": 90}})
        coord.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_no_update_when_data_unchanged(self):
        coord = _make_coordinator(device_data={"BatteryMSG": {"capacity": 90}})
        coord._on_device_status("yarbo/SN001/device", {"BatteryMSG": {"capacity": 90}})
        coord.hass.loop.call_soon_threadsafe.assert_not_called()

    def test_ignores_malformed_topic(self):
        coord = _make_coordinator()
        coord._on_device_status("no_slash", {"a": 1})
        assert coord.data is None  # nothing created


# ---------------------------------------------------------------------------
# _on_heart_beat
# ---------------------------------------------------------------------------


class TestOnHeartBeat:
    def test_sets_online_true(self):
        coord = _make_coordinator()
        coord._on_heart_beat("yarbo/SN001/heartbeat", {"seq": 1})
        assert coord.data[SN]["__online__"] is True

    def test_updates_heartbeat_timestamp(self):
        coord = _make_coordinator()
        before = time.monotonic()
        coord._on_heart_beat("yarbo/SN001/heartbeat", {"seq": 1})
        assert coord._last_heartbeat[SN] >= before

    def test_triggers_update_on_first_heartbeat(self):
        coord = _make_coordinator()
        coord._on_heart_beat("yarbo/SN001/heartbeat", {"seq": 1})
        coord.hass.loop.call_soon_threadsafe.assert_called()

    def test_no_update_when_payload_unchanged(self):
        coord = _make_coordinator(
            device_data={"__online__": True, "HeartBeatMSG": {"seq": 1}}
        )
        coord._last_heartbeat[SN] = time.monotonic()
        coord._on_heart_beat("yarbo/SN001/heartbeat", {"seq": 1})
        coord.hass.loop.call_soon_threadsafe.assert_not_called()

    def test_online_transition_triggers_update(self):
        coord = _make_coordinator(device_data={"__online__": False})
        coord._on_heart_beat("yarbo/SN001/heartbeat", {"seq": 1})
        coord.hass.loop.call_soon_threadsafe.assert_called()


# ---------------------------------------------------------------------------
# _async_check_heartbeats
# ---------------------------------------------------------------------------


class TestAsyncCheckHeartbeats:
    @pytest.mark.asyncio
    async def test_marks_offline_when_timed_out(self):
        coord = _make_coordinator(device_data={"__online__": True})
        device = MagicMock()
        device.sn = SN
        coord.devices = [device]
        coord._last_heartbeat[SN] = time.monotonic() - 100  # past 90s timeout
        with patch.object(type(coord), "async_set_updated_data"):
            await coord._async_check_heartbeats()
        assert coord.data[SN]["__online__"] is False

    @pytest.mark.asyncio
    async def test_no_change_when_heartbeat_recent(self):
        coord = _make_coordinator(device_data={"__online__": True})
        device = MagicMock()
        device.sn = SN
        coord.devices = [device]
        coord._last_heartbeat[SN] = time.monotonic()
        with patch.object(type(coord), "async_set_updated_data") as mock_update:
            await coord._async_check_heartbeats()
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_data_is_noop(self):
        coord = _make_coordinator()
        await coord._async_check_heartbeats()

    @pytest.mark.asyncio
    async def test_already_offline_not_double_marked(self):
        coord = _make_coordinator(device_data={"__online__": False})
        device = MagicMock()
        device.sn = SN
        coord.devices = [device]
        coord._last_heartbeat[SN] = time.monotonic() - 100
        with patch.object(type(coord), "async_set_updated_data") as mock_update:
            await coord._async_check_heartbeats()
        mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# _persist_maps / _async_restore_maps
# ---------------------------------------------------------------------------


class TestMapPersistence:
    def test_persist_maps_schedules_save(self):
        coord = _make_coordinator()
        coord._map_data = {SN: {"type": "FeatureCollection", "features": []}}
        coord._gps_refs = {SN: {"rtkFixType": 1}}
        coord._persist_maps()
        coord._map_store.async_delay_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_maps_loads_stored_data(self):
        coord = _make_coordinator()
        stored = {
            "map_data": {SN: {"type": "FeatureCollection", "features": []}},
            "gps_refs": {SN: {"rtkFixType": 1}},
        }
        coord._map_store.async_load = AsyncMock(return_value=stored)
        await coord._async_restore_maps()
        assert SN in coord._map_data
        assert SN in coord._gps_refs

    @pytest.mark.asyncio
    async def test_restore_maps_handles_empty_store(self):
        coord = _make_coordinator()
        coord._map_store.async_load = AsyncMock(return_value=None)
        await coord._async_restore_maps()  # no-op, no error

    @pytest.mark.asyncio
    async def test_restore_maps_handles_storage_error(self):
        coord = _make_coordinator()
        coord._map_store.async_load = AsyncMock(side_effect=Exception("storage down"))
        await coord._async_restore_maps()  # logs warning, no crash
