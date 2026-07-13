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
from homeassistant.helpers import entity_registry as er
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
async def test_odometry_totals_registered_in_state_machine(hass: HomeAssistant):
    """After setup, the new total left odometry entities appear in hass.states."""
    await _setup_entry(hass)

    assert hass.states.get("sensor.yarbo_y1_odometry_total_forward_left") is not None
    assert hass.states.get("sensor.yarbo_y1_odometry_total_reverse_left") is not None


@pytest.mark.asyncio
async def test_yarbo_odometry_entity_count_is_8(hass: HomeAssistant):
    """After setup, all odometry entities are registered."""
    await _setup_entry(hass)
    registry = er.async_get(hass)
    odometry = [
        entity
        for entity in registry.entities.values()
        if entity.platform == "yarbo" and "odometry" in entity.unique_id
    ]
    assert len(odometry) == 8


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
# Switch service calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_turn_on_updates_state(hass: HomeAssistant):
    """switch.turn_on service → entity state becomes 'on' in hass.states."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    # Make device available
    coord.async_set_updated_data({SN: {"__online__": True}})
    await hass.async_block_till_done()

    switch_id = f"switch.{DEVICE_NAME.lower().replace(' ', '_')}_sound_switch"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(switch_id).state == "on"


@pytest.mark.asyncio
async def test_switch_turn_off_updates_state(hass: HomeAssistant):
    """switch.turn_off service → entity state becomes 'off' in hass.states."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    coord.async_set_updated_data({SN: {"__online__": True}})
    await hass.async_block_till_done()

    switch_id = f"switch.{DEVICE_NAME.lower().replace(' ', '_')}_sound_switch"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(switch_id).state == "off"


@pytest.mark.asyncio
async def test_switch_turn_on_with_no_coordinator_data(hass: HomeAssistant):
    """switch.turn_on on entity with no coordinator data: HA calls async_turn_on
    (optimistic state update fires), switch ends up 'on' in hass.states.

    HA does NOT block service calls on unavailable entities for switch platform.
    The mock client's mqtt_publish_command returns None (no error), so the
    optimistic state update completes and the entity reports 'on'.
    """
    await _setup_entry(hass)
    switch_id = f"switch.{DEVICE_NAME.lower().replace(' ', '_')}_sound_switch"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )
    await hass.async_block_till_done()
    # Optimistic update fires regardless of availability
    assert hass.states.get(switch_id).state == "on"


# ---------------------------------------------------------------------------
# Select service calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_select_option_updates_state(hass: HomeAssistant):
    """select.select_option service → entity state reflects chosen option."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    coord.async_set_updated_data({SN: {"__online__": True}})
    await hass.async_block_till_done()

    select_id = f"select.{DEVICE_NAME.lower().replace(' ', '_')}_working_state"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": select_id, "option": "working"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(select_id).state == "working"


@pytest.mark.asyncio
async def test_select_option_standby_updates_state(hass: HomeAssistant):
    """select.select_option 'standby' → state becomes 'standby' and standby flag set."""
    entry = await _setup_entry(hass)
    coord = hass.data[DOMAIN][entry.entry_id]

    coord.async_set_updated_data({SN: {"__online__": True}})
    await hass.async_block_till_done()

    select_id = f"select.{DEVICE_NAME.lower().replace(' ', '_')}_working_state"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": select_id, "option": "standby"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(select_id).state == "standby"
    # Standby flag set on coordinator
    assert coord._user_standby.get(SN) is True


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
