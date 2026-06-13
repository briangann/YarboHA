"""Tests for YarboDataUpdateCoordinator.async_setup.

Mocks YarboClient so no real SDK/MQTT/network connection is needed.
Uses the real hass fixture for async_add_executor_job.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yarbo.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    DATA_ACCESS_TOKEN,
    DATA_REFRESH_TOKEN,
    DOMAIN,
)
from custom_components.yarbo.coordinator import YarboDataUpdateCoordinator

EMAIL = "user@example.com"
TOKEN = "tok"
REFRESH = "ref"


def _fake_device(sn="SN001", type_id="T01", name="Yarbo Y1", model="Y1"):
    d = MagicMock()
    d.sn = sn
    d.type_id = type_id
    d.name = name
    d.model = model
    return d


def _mock_client(devices=None):
    """Build a minimal YarboClient mock."""
    client = MagicMock()
    client.token = TOKEN
    client.refresh_token = REFRESH
    client.restore_session.return_value = None
    client.login.return_value = None
    client.get_devices.return_value = devices or [_fake_device()]
    client.mqtt_connect.return_value = None
    client.subscribe_device_message.return_value = None
    client.subscribe_heart_beat.return_value = None
    client.subscribe_data_feedback.return_value = None
    client.close.return_value = None
    return client


def _make_entry(hass, options=None, data=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data
        or {
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: "secret",
            DATA_ACCESS_TOKEN: TOKEN,
            DATA_REFRESH_TOKEN: REFRESH,
        },
        options=options if options is not None else {CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)
    return entry


# ---------------------------------------------------------------------------
# Happy-path setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_happy_path(hass: HomeAssistant):
    entry = _make_entry(hass)
    client = _mock_client()

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    assert coord._client is client
    assert len(coord.devices) == 1
    assert coord.devices[0].sn == "SN001"
    client.restore_session.assert_called_once()
    client.mqtt_connect.assert_called_once()
    client.subscribe_device_message.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_login_fallback_when_no_tokens(hass: HomeAssistant):
    """No stored tokens → falls back to client.login."""
    entry = _make_entry(
        hass,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: "secret"},
    )
    client = _mock_client()

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    client.login.assert_called_once_with(EMAIL, "secret")
    client.restore_session.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_filters_devices_by_selection(hass: HomeAssistant):
    """Only selected SNs appear in coord.devices."""
    entry = _make_entry(hass, options={CONF_SELECTED_DEVICES: ["SN002"]})
    client = _mock_client(devices=[_fake_device("SN001"), _fake_device("SN002")])

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    assert len(coord.devices) == 1
    assert coord.devices[0].sn == "SN002"


@pytest.mark.asyncio
async def test_async_setup_all_devices_when_no_selection(hass: HomeAssistant):
    """Empty selection list → all discovered devices."""
    entry = _make_entry(hass, options={})
    client = _mock_client(devices=[_fake_device("SN001"), _fake_device("SN002")])

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    assert len(coord.devices) == 2


@pytest.mark.asyncio
async def test_async_setup_mqtt_failure_is_non_fatal(hass: HomeAssistant):
    """MQTT connect failure is logged as warning — setup completes."""
    from yarbo_robot_sdk import YarboSDKError

    entry = _make_entry(hass)
    client = _mock_client()
    client.mqtt_connect.side_effect = YarboSDKError("broker down")

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    assert coord._client is client


@pytest.mark.asyncio
async def test_async_setup_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
):
    """AuthenticationError during restore_session → ConfigEntryAuthFailed."""
    from yarbo_robot_sdk import AuthenticationError

    entry = _make_entry(hass)
    client = _mock_client()
    client.restore_session.side_effect = AuthenticationError("expired")

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        coord = YarboDataUpdateCoordinator(hass, entry)
        with pytest.raises(ConfigEntryAuthFailed):
            await coord.async_setup()


@pytest.mark.asyncio
async def test_async_setup_token_expired_on_get_devices_raises(hass: HomeAssistant):
    """TokenExpiredError on get_devices → ConfigEntryAuthFailed."""
    from yarbo_robot_sdk import TokenExpiredError

    entry = _make_entry(hass)
    client = _mock_client()
    client.get_devices.side_effect = TokenExpiredError("expired")

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        coord = YarboDataUpdateCoordinator(hass, entry)
        with patch.object(coord, "_async_restore_maps", new=AsyncMock()):
            with pytest.raises(ConfigEntryAuthFailed):
                await coord.async_setup()


@pytest.mark.asyncio
async def test_async_setup_heartbeat_subscription_failure_non_fatal(
    hass: HomeAssistant,
):
    """Heart beat subscription failure is a warning — setup continues."""
    from yarbo_robot_sdk import YarboSDKError

    entry = _make_entry(hass)
    client = _mock_client()
    client.subscribe_heart_beat.side_effect = YarboSDKError("sub failed")

    with patch("custom_components.yarbo.coordinator.YarboClient", return_value=client):
        with patch("custom_components.yarbo.coordinator.async_track_time_interval"):
            coord = YarboDataUpdateCoordinator(hass, entry)
            with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
                with patch.object(coord.entry, "async_create_background_task"):
                    await coord.async_setup()

    assert coord._client is client
