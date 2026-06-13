"""Test: _async_initial_data_fetch must call async_set_updated_data even when all
device fetches time out (device offline at startup).

Without the fix, data stays None, async_set_updated_data is never called,
and entities remain in "unknown" state instead of "unavailable".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.yarbo.coordinator import YarboDataUpdateCoordinator

SN = "SN001"


def _make_coordinator_with_device(sn=SN):
    coord = YarboDataUpdateCoordinator.__new__(YarboDataUpdateCoordinator)
    coord.hass = MagicMock()
    coord.entry = MagicMock()
    coord.entry.options = {}
    coord.logger = MagicMock()
    coord.name = "yarbo"
    coord.update_interval = None
    coord._listeners = {}
    coord._unsub_refresh = None
    coord.data = None  # starts None — the bug condition
    coord._client = MagicMock()
    device = MagicMock()
    device.sn = sn
    device.type_id = "T01"
    coord.devices = [device]
    coord._device_msg_inflight = set()
    coord._device_msg_loaded = set()
    coord._wifi_inflight = set()
    coord._wifi_loaded = set()
    coord._plan_data = {}
    coord._gps_refs = {}
    coord._map_data = {}
    coord._selected_plan = {}
    coord._user_standby = {}
    coord._last_heartbeat = {}
    coord._standby_store = MagicMock()
    coord._map_store = MagicMock()
    return coord


# ---------------------------------------------------------------------------
# Reproduce the bug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initial_fetch_notifies_entities_when_device_offline():
    """When all fetches time out, data is None.

    BUG: async_set_updated_data is never called → entities stay 'unknown'.
    FIXED: data is initialised to {} and async_set_updated_data is always called.
    """
    coord = _make_coordinator_with_device()

    # All four fetch methods time out — data stays None
    coord._async_fetch_device_msg = AsyncMock()  # no-op, doesn't set self.data
    coord._async_fetch_wifi_info = AsyncMock()
    coord._async_fetch_plans = AsyncMock()
    coord._async_fetch_gps_ref = AsyncMock()

    with patch.object(type(coord), "async_set_updated_data") as mock_notify:
        await coord._async_initial_data_fetch()

    # Must always notify entities after the initial fetch pass
    mock_notify.assert_called_once()
    # data must not be None — entities evaluate availability against it
    assert coord.data is not None, "data must not be None after initial fetch"
    assert coord.data == {}, "data should be empty dict, not None"


@pytest.mark.asyncio
async def test_initial_fetch_notifies_when_device_online():
    """Happy path: device responds, data is populated, entities notified."""
    coord = _make_coordinator_with_device()

    async def _fake_fetch_device_msg(sn, type_id):
        # Simulate successful fetch setting self.data
        coord.data = {sn: {"StateMSG": {"battery": 85}, "__online__": True}}

    coord._async_fetch_device_msg = _fake_fetch_device_msg
    coord._async_fetch_wifi_info = AsyncMock()
    coord._async_fetch_plans = AsyncMock()
    coord._async_fetch_gps_ref = AsyncMock()

    with patch.object(type(coord), "async_set_updated_data") as mock_notify:
        await coord._async_initial_data_fetch()

    mock_notify.assert_called_once()
    assert coord.data[SN]["__online__"] is True


@pytest.mark.asyncio
async def test_initial_fetch_partial_fetch_still_notifies():
    """One device offline, one online — entities still get updated."""
    coord = _make_coordinator_with_device()
    sn2 = "SN002"
    d2 = MagicMock()
    d2.sn = sn2
    d2.type_id = "T01"
    coord.devices.append(d2)

    calls = []

    async def _fake_fetch(sn, type_id):
        if sn == SN:
            # SN001 online
            if coord.data is None:
                coord.data = {}
            coord.data[sn] = {"__online__": True}
        # SN002 times out — no data added
        calls.append(sn)

    coord._async_fetch_device_msg = _fake_fetch
    coord._async_fetch_wifi_info = AsyncMock()
    coord._async_fetch_plans = AsyncMock()
    coord._async_fetch_gps_ref = AsyncMock()

    with patch.object(type(coord), "async_set_updated_data") as mock_notify:
        await coord._async_initial_data_fetch()

    assert mock_notify.call_count == 1
    assert SN in coord.data
    assert sn2 not in coord.data  # SN002 timed out, no data for it
