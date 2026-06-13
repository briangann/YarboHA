"""Tests for custom_components/yarbo/__init__.py setup/unload entry points."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yarbo.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    DATA_ACCESS_TOKEN,
    DATA_REFRESH_TOKEN,
    DOMAIN,
)

EMAIL = "user@example.com"
TOKEN = "tok"
REFRESH = "ref"


def _fake_device(sn="SN001"):
    d = MagicMock()
    d.sn = sn
    d.type_id = "T01"
    d.name = "Yarbo Y1"
    d.model = "Y1"
    return d


def _mock_client(devices=None):
    client = MagicMock()
    client.token = TOKEN
    client.refresh_token = REFRESH
    client.restore_session.return_value = None
    client.get_devices.return_value = devices or [_fake_device()]
    client.mqtt_connect.return_value = None
    client.subscribe_device_message.return_value = None
    client.subscribe_heart_beat.return_value = None
    client.subscribe_data_feedback.return_value = None
    client.close.return_value = None
    return client


def _make_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: "secret",
            DATA_ACCESS_TOKEN: TOKEN,
            DATA_REFRESH_TOKEN: REFRESH,
        },
        options={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_registers_coordinator(hass: HomeAssistant):
    """async_setup_entry registers coordinator in hass.data[DOMAIN]."""
    entry = _make_entry(hass)
    client = _mock_client()

    with (
        patch("custom_components.yarbo.coordinator.YarboClient", return_value=client),
        patch("custom_components.yarbo.coordinator.async_track_time_interval"),
        patch(
            "custom_components.yarbo.coordinator.YarboDataUpdateCoordinator._async_restore_standby",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.yarbo.coordinator.YarboDataUpdateCoordinator._async_initial_data_fetch",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_unload_entry_removes_coordinator(hass: HomeAssistant):
    """async_unload_entry removes coordinator from hass.data and calls shutdown."""
    entry = _make_entry(hass)
    client = _mock_client()

    with (
        patch("custom_components.yarbo.coordinator.YarboClient", return_value=client),
        patch("custom_components.yarbo.coordinator.async_track_time_interval"),
        patch(
            "custom_components.yarbo.coordinator.YarboDataUpdateCoordinator._async_restore_standby",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.yarbo.coordinator.YarboDataUpdateCoordinator._async_initial_data_fetch",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            hass.data[DOMAIN][entry.entry_id], "async_shutdown", new=AsyncMock()
        ),
    ):
        unloaded = await hass.config_entries.async_unload(entry.entry_id)

    assert unloaded is True
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
