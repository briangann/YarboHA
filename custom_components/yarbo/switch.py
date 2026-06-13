"""Switch platform for Yarbo integration — configuration-driven."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YarboDataUpdateCoordinator
from .entity_filters import control_matches_device

_LOGGER = logging.getLogger(__name__)

# Seconds to ignore coordinator updates after sending a command,
# preventing UI flicker from stale DeviceMSG data.
COMMAND_COOLDOWN_SECONDS = 15
FOLLOW_KEEPALIVE_INTERVAL = timedelta(seconds=5)
FOLLOW_STATE_PATH = "StateMSG.robot_follow_state"
FOLLOW_STATE_TOPIC = "set_follow_state"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo switch entities from SDK control field definitions."""
    from yarbo_robot_sdk import get_control_field_definitions

    coordinator: YarboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    for device in coordinator.devices:
        ctrl_defs = await hass.async_add_executor_job(
            get_control_field_definitions, device.type_id
        )
        for ctrl_def in ctrl_defs:
            if ctrl_def.entity_type == "switch" and control_matches_device(
                coordinator, device, ctrl_def
            ):
                entities.append(YarboConfigSwitch(coordinator, device, ctrl_def))

    async_add_entities(entities)


class YarboConfigSwitch(CoordinatorEntity[YarboDataUpdateCoordinator], SwitchEntity):
    """Configuration-driven switch entity for sound and light control."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, ctrl_def) -> None:
        super().__init__(coordinator)
        self._device = device
        self._ctrl_def = ctrl_def
        self._command_sent_at: float = 0  # monotonic timestamp of last command
        self._follow_keepalive_unsub: CALLBACK_TYPE | None = None

        path_key = ctrl_def.path.replace(".", "_").replace("__", "").lower()
        self._attr_unique_id = f"{device.sn}_{path_key}_switch"
        self._attr_name = ctrl_def.name
        self._attr_entity_registry_enabled_default = ctrl_def.enabled_by_default
        self._attr_is_on: bool | None = None

        if ctrl_def.icon:
            self._attr_icon = ctrl_def.icon

    @property
    def _is_follow_mode_switch(self) -> bool:
        return (
            self._ctrl_def.path == FOLLOW_STATE_PATH
            and self._ctrl_def.command_topic == FOLLOW_STATE_TOPIC
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync switch state from coordinator data.

        Skips state sync during the cooldown period after a command to prevent
        UI flicker from stale DeviceMSG data arriving before the device
        processes the command.
        """
        if time.monotonic() - self._command_sent_at < COMMAND_COOLDOWN_SECONDS:
            # Within cooldown — keep optimistic state, just refresh HA state
            self.async_write_ha_state()
            return

        raw = self._get_state_value()
        if raw is not None:
            if self._ctrl_def.command_builder == "light_switch":
                new_state = raw != 0 and raw is not False
            else:
                new_state = bool(raw)
            if new_state != self._attr_is_on:
                self._attr_is_on = new_state
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        self._attr_is_on = True
        self.async_write_ha_state()
        await self._async_send_command(True)
        self._start_follow_keepalive()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        self._stop_follow_keepalive()
        self._attr_is_on = False
        self.async_write_ha_state()
        await self._async_send_command(False)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up timers when Home Assistant unloads the entity."""
        self._stop_follow_keepalive()

    async def _async_send_command(
        self,
        turn_on: bool,
        *,
        raise_errors: bool = True,
        update_cooldown: bool = True,
    ) -> None:
        """Send the MQTT command, routing through typed SDK methods where available."""
        if update_cooldown:
            self._command_sent_at = time.monotonic()
        try:
            bound = self.coordinator.bound_device(self._device.sn)
            if bound is not None and await self._dispatch_typed(bound, turn_on):
                return
            # fallback: use core.publish_command for builders without a typed method
            payload = self._build_payload(turn_on)
            _LOGGER.debug(
                "[switch] publish sn=%s topic=%s payload=%s",
                self._device.sn,
                self._ctrl_def.command_topic,
                payload,
            )
            client = self.coordinator._client
            if client is None:
                raise HomeAssistantError(
                    f"Cannot send {self._ctrl_def.name}: not connected"
                )
            await self.hass.async_add_executor_job(
                client.core.publish_command,
                self._device.sn,
                self._ctrl_def.command_topic,
                payload,
                self._device.type_id,
            )
        except Exception as exc:
            _LOGGER.error("[switch] command FAILED: %s", exc)
            self._handle_coordinator_update()
            if not raise_errors:
                return
            raise HomeAssistantError(
                f"Failed to send {self._ctrl_def.name} command: {exc}"
            ) from exc

    async def _dispatch_typed(self, bound, turn_on: bool) -> bool:
        """Route to a typed SDK method. Returns True if dispatched."""
        builder = self._ctrl_def.command_builder
        if builder == "sound_switch":
            current_vol = self._get_sibling_value("StateMSG.volume")
            vol = round(float(current_vol), 1) if current_vol is not None else 1.0
            await self.hass.async_add_executor_job(
                bound.core.set_sound_param, turn_on, vol
            )
            return True
        if builder == "light_switch":
            await self.hass.async_add_executor_job(bound.core.set_headlight, turn_on)
            return True
        if builder == "person_detection_switch":
            await self.hass.async_add_executor_job(
                bound.core.set_person_detect, turn_on
            )
            return True
        if (
            builder == "state_int_switch"
            and self._ctrl_def.command_topic == "set_follow_state"
        ):
            await self.hass.async_add_executor_job(bound.core.set_follow_state, turn_on)
            return True
        if (
            builder == "state_bool_switch"
            and self._ctrl_def.command_topic == "set_child_lock"
        ):
            await self.hass.async_add_executor_job(bound.core.set_child_lock, turn_on)
            return True
        if builder == "geo_fence_switch":
            await self.hass.async_add_executor_job(
                bound.core.save_global_params, turn_on
            )
            return True
        if builder == "ignore_obstacles_switch":
            await self.hass.async_add_executor_job(
                bound.core.set_map_obstacle_switch, turn_on
            )
            return True
        return False

    def _start_follow_keepalive(self) -> None:
        """Keep Follow Mode alive; the mobile app republishes this command too."""
        if not self._is_follow_mode_switch or self._follow_keepalive_unsub is not None:
            return
        self._follow_keepalive_unsub = async_track_time_interval(
            self.hass, self._async_follow_keepalive, FOLLOW_KEEPALIVE_INTERVAL
        )

    def _stop_follow_keepalive(self) -> None:
        if self._follow_keepalive_unsub is None:
            return
        self._follow_keepalive_unsub()
        self._follow_keepalive_unsub = None

    async def _async_follow_keepalive(self, _now) -> None:
        if self._attr_is_on is not True:
            self._stop_follow_keepalive()
            return
        await self._async_send_command(True, raise_errors=False, update_cooldown=False)

    def _build_payload(self, turn_on: bool) -> dict:
        """Build command payload based on command_builder type."""
        builder = self._ctrl_def.command_builder
        if builder == "sound_switch":
            current_vol = self._get_sibling_value("StateMSG.volume")
            vol = round(float(current_vol), 1) if current_vol is not None else 1.0
            return {"enable": turn_on, "vol": vol, "mode": 0}
        elif builder == "light_switch":
            return {"led_head": 1 if turn_on else 0}
        elif builder == "person_detection_switch":
            return {"state": 1 if turn_on else 0}
        elif builder == "state_int_switch":
            return {"state": 1 if turn_on else 0}
        elif builder == "state_bool_switch":
            return {"state": turn_on}
        elif builder == "geo_fence_switch":
            return {"id": 1, "enable_elec_fence": turn_on}
        elif builder == "ignore_obstacles_switch":
            return {"switch": 1 if turn_on else 0}
        raise HomeAssistantError(f"Unsupported switch command builder: {builder}")

    def _get_state_value(self):
        """Extract current state value from coordinator data."""
        if not self.coordinator.data:
            return None
        device_data = self.coordinator.data.get(self._device.sn)
        if device_data is None:
            return None
        from yarbo_robot_sdk.device_helpers import extract_field

        return extract_field(device_data, self._ctrl_def.path)

    def _get_sibling_value(self, field_path: str):
        """Extract a sibling field value from coordinator data."""
        if not self.coordinator.data:
            return None
        device_data = self.coordinator.data.get(self._device.sn)
        if device_data is None:
            return None
        from yarbo_robot_sdk.device_helpers import extract_field

        return extract_field(device_data, field_path)
