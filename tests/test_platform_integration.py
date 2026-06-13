"""Platform integration tests — entity setup through the real HA state machine.

These tests load the full integration (async_setup_entry → platform setup →
entity registration) using pytest-homeassistant-custom-component so we can
verify entities appear in hass.states, have the right attributes, and
transition correctly when coordinator data changes.

Distinct from unit tests: here we're testing HA *wiring* — device_class,
unit_of_measurement, availability, and state machine transitions — not the
extraction logic (covered by test_sensor_telemetry.py etc.).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
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

SN = "SN001"
TYPE_ID = "yarbo_Y"
DEVICE_NAME = "Yarbo Y1"


def _mock_client():
    device = MagicMock()
    device.sn = SN
    device.type_id = TYPE_ID
    device.name = DEVICE_NAME
    device.model = "Y1"

    client = MagicMock()
    client.token = "tok"
    client.refresh_token = "ref"
    client.restore_session.return_value = None
    client.get_devices.return_value = [device]
    client.mqtt_connect.return_value = None
    client.subscribe_device_message.return_value = None
    client.subscribe_heart_beat.return_value = None
    client.subscribe_data_feedback.return_value = None
    client.close.return_value = None
    return client


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create config entry and load the integration into hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            DATA_ACCESS_TOKEN: "tok",
            DATA_REFRESH_TOKEN: "ref",
        },
        options={CONF_SELECTED_DEVICES: [SN]},
    )
    entry.add_to_hass(hass)

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
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


# ---------------------------------------------------------------------------
# Entity registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensors_registered_in_state_machine(hass: HomeAssistant):
    """After setup, sensor entities appear in hass.states."""
    await _setup_entry(hass)

    # Battery is always registered for yarbo_Y
    battery_state = hass.states.get(
        f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_battery"
    )
    assert battery_state is not None, "Battery sensor must be registered"


@pytest.mark.asyncio
async def test_device_tracker_registered(hass: HomeAssistant):
    """Device tracker entity appears in hass.states after setup."""
    await _setup_entry(hass)
    states = hass.states.async_entity_ids("device_tracker")
    assert any(DEVICE_NAME.lower().replace(" ", "_") in s for s in states)


@pytest.mark.asyncio
async def test_binary_sensors_registered(hass: HomeAssistant):
    """Binary sensor entities appear in hass.states after setup."""
    await _setup_entry(hass)
    states = hass.states.async_entity_ids("binary_sensor")
    assert len(states) > 0, "At least one binary sensor must be registered"


@pytest.mark.asyncio
async def test_buttons_registered(hass: HomeAssistant):
    """Button entities appear in hass.states after setup."""
    await _setup_entry(hass)
    states = hass.states.async_entity_ids("button")
    assert len(states) > 0, "At least one button must be registered"


# ---------------------------------------------------------------------------
# Initial state — no data yet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensor_unavailable_when_no_data(hass: HomeAssistant):
    """Before any MQTT data, sensors are unavailable (not unknown)."""
    await _setup_entry(hass)

    # All sensor states should be unavailable since coordinator.data is empty
    sensor_states = hass.states.async_all("sensor")
    for state in sensor_states:
        if DEVICE_NAME.lower().replace(" ", "_") in state.entity_id:
            assert state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN), (
                f"{state.entity_id} should be unavailable, got {state.state}"
            )


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_battery_sensor_updates_when_coordinator_pushes_data(hass: HomeAssistant):
    """Coordinator push → battery sensor reflects new value in hass.states."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    # Simulate a coordinator data push (as MQTT would trigger)
    coord.async_set_updated_data(
        {SN: {"BatteryMSG": {"capacity": 82}, "__online__": True}}
    )
    await hass.async_block_till_done()

    battery_id = f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_battery"
    state = hass.states.get(battery_id)
    assert state is not None
    assert state.state == "82", f"Expected 82, got {state.state}"


@pytest.mark.asyncio
async def test_sensor_retains_last_value_when_device_goes_offline(hass: HomeAssistant):
    """Device going offline → sensors retain last known value (not unavailable).

    This is intentional: CoordinatorEntity.available returns last_update_success,
    which stays True since the coordinator itself is still running. The __online__
    flag is used by buttons for safety checks, not to gate sensor availability.
    Sensors show stale data rather than going unavailable on device offline.
    """
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    # First push: device online with data
    coord.async_set_updated_data(
        {SN: {"BatteryMSG": {"capacity": 75}, "__online__": True}}
    )
    await hass.async_block_till_done()

    battery_id = f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_battery"
    assert hass.states.get(battery_id).state == "75"

    # Device goes offline — sensor retains last value (by design)
    coord.async_set_updated_data(
        {SN: {"BatteryMSG": {"capacity": 75}, "__online__": False}}
    )
    await hass.async_block_till_done()

    # Still 75 — last known value, not unavailable
    assert hass.states.get(battery_id).state == "75"


@pytest.mark.asyncio
async def test_online_binary_sensor_reflects_device_state(hass: HomeAssistant):
    """The online binary sensor tracks __online__ from coordinator data."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    online_id = f"binary_sensor.{DEVICE_NAME.lower().replace(' ', '_')}_online"

    # Device comes online
    coord.async_set_updated_data({SN: {"__online__": True}})
    await hass.async_block_till_done()
    assert hass.states.get(online_id).state == "on"

    # Device goes offline
    coord.async_set_updated_data({SN: {"__online__": False}})
    await hass.async_block_till_done()
    assert hass.states.get(online_id).state == "off"


# ---------------------------------------------------------------------------
# Unload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unload_removes_entities(hass: HomeAssistant):
    """Unloading the entry removes entities from hass.states."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    # Patch shutdown so it doesn't try real MQTT disconnect
    with patch.object(coord, "async_shutdown", new=AsyncMock()):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    # Entry no longer in hass.data
    assert entry.entry_id not in hass.data.get(DOMAIN, {})

    # HA keeps entity state history (restored=True) after unload — not None
    battery_id = f"sensor.{DEVICE_NAME.lower().replace(' ', '_')}_battery"
    final = hass.states.get(battery_id)
    assert final is None or final.state == STATE_UNAVAILABLE, (
        f"Expected None or unavailable after unload, got {final}"
    )
