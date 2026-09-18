"""Tests for Yarbo repair issue and notification surfacing."""

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
from custom_components.yarbo.coordinator import YarboDataUpdateCoordinator

EMAIL = "user@example.com"
TOKEN = "tok"
REFRESH = "ref"
SN = "SN001"


def _close_background_task(hass, coro, **kwargs):
    coro.close()


def _fake_device(sn=SN, type_id="T01", name="Yarbo Y1", model="Y1"):
    device = MagicMock()
    device.sn = sn
    device.type_id = type_id
    device.name = name
    device.model = model
    return device


def _mock_client():
    client = MagicMock()
    client.token = TOKEN
    client.refresh_token = REFRESH
    client.restore_session.return_value = None
    client.login.return_value = None
    client.get_devices.return_value = [_fake_device()]
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
        options={CONF_SELECTED_DEVICES: [SN]},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_mqtt_not_authorized_creates_repair_and_notification(hass: HomeAssistant):
    """MQTT auth failure should surface in Repairs and persistent notifications."""
    from yarbo_robot_sdk import YarboSDKError

    entry = _make_entry(hass)
    client = _mock_client()
    client.mqtt_connect.side_effect = YarboSDKError("Not authorized")

    with (
        patch("custom_components.yarbo.coordinator.YarboClient", return_value=client),
        patch("custom_components.yarbo.coordinator.async_track_time_interval"),
        patch(
            "custom_components.yarbo.coordinator.ir.async_create_issue"
        ) as create_issue,
        patch(
            "custom_components.yarbo.coordinator.async_create_notification"
        ) as create_notification,
        patch(
            "custom_components.yarbo.coordinator.async_dismiss_notification"
        ) as dismiss_notification,
    ):
        coord = YarboDataUpdateCoordinator(hass, entry)
        with patch.object(coord, "_async_restore_standby", new=AsyncMock()):
            with patch.object(
                coord.entry,
                "async_create_background_task",
                side_effect=_close_background_task,
            ):
                await coord.async_setup()

    create_issue.assert_called_once()
    create_notification.assert_called_once()
    dismiss_notification.assert_not_called()


@pytest.mark.asyncio
async def test_force_relogin_clears_repair_and_notification(hass: HomeAssistant):
    """Successful relogin should clear the UI issue and notification."""
    entry = _make_entry(hass)
    client = _mock_client()

    with (
        patch("custom_components.yarbo.coordinator.YarboClient", return_value=client),
        patch("custom_components.yarbo.coordinator.async_track_time_interval"),
        patch(
            "custom_components.yarbo.coordinator.ir.async_delete_issue"
        ) as delete_issue,
        patch(
            "custom_components.yarbo.coordinator.async_dismiss_notification"
        ) as dismiss_notification,
    ):
        coord = YarboDataUpdateCoordinator(hass, entry)
        coord._client = client
        await coord.async_force_relogin()

    delete_issue.assert_called_once()
    dismiss_notification.assert_called_once()
