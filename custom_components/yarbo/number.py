"""Number platform for Yarbo integration — configuration-driven + Plan Start Percent."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YarboDataUpdateCoordinator
from .entity_filters import control_matches_device

_LOGGER = logging.getLogger(__name__)

COMMAND_COOLDOWN_SECONDS = 5
BLADE_SPEED_KEEPALIVE_INTERVAL = timedelta(milliseconds=200)
BLADE_SPEED_TOPIC = "mower_speed_cmd"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo number entities from SDK control field definitions."""
    from yarbo_robot_sdk import get_control_field_definitions

    coordinator: YarboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []
    head_control_defs = []
    added_head_control_ids: set[str] = set()
    for device in coordinator.devices:
        ctrl_defs = await hass.async_add_executor_job(
            get_control_field_definitions, device.type_id
        )
        for ctrl_def in ctrl_defs:
            if ctrl_def.entity_type != "number":
                continue
            if getattr(ctrl_def, "compatible_head_types", None):
                head_control_defs.append((device, ctrl_def))
                continue
            entities.append(YarboConfigNumber(coordinator, device, ctrl_def))

        # Hardcoded Plan Start Percent (local-only, no MQTT state)
        entities.append(YarboPlanStartPercent(coordinator, device))

    async_add_entities(entities)

    @callback
    def async_add_matching_head_controls() -> None:
        """Add head-specific number controls once the device head is known."""
        new_entities: list[NumberEntity] = []
        for device, ctrl_def in head_control_defs:
            unique_id = _control_unique_id(device, ctrl_def)
            if unique_id in added_head_control_ids:
                continue
            if not control_matches_device(coordinator, device, ctrl_def):
                continue
            added_head_control_ids.add(unique_id)
            new_entities.append(YarboConfigNumber(coordinator, device, ctrl_def))
            _LOGGER.info(
                "Adding %s control for %s after matching head type",
                ctrl_def.name,
                device.sn,
            )
        if new_entities:
            async_add_entities(new_entities)

    if head_control_defs:
        async_add_matching_head_controls()
        entry.async_on_unload(
            coordinator.async_add_listener(async_add_matching_head_controls)
        )


def _control_unique_id(device, ctrl_def) -> str:
    path_key = ctrl_def.path.replace(".", "_").replace("__", "").lower()
    return f"{device.sn}_{path_key}_number"


class YarboConfigNumber(
    CoordinatorEntity[YarboDataUpdateCoordinator], NumberEntity
):
    """Configuration-driven number entity."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, device, ctrl_def) -> None:
        super().__init__(coordinator)
        self._device = device
        self._ctrl_def = ctrl_def
        self._command_sent_at: float = 0
        self._optimistic_value: float | None = None
        self._blade_speed_keepalive_unsub: CALLBACK_TYPE | None = None

        self._attr_unique_id = _control_unique_id(device, ctrl_def)
        self._attr_name = ctrl_def.name
        self._attr_entity_registry_enabled_default = ctrl_def.enabled_by_default

        if ctrl_def.min_value is not None:
            self._attr_native_min_value = ctrl_def.min_value
        if ctrl_def.max_value is not None:
            self._attr_native_max_value = ctrl_def.max_value
        if ctrl_def.step is not None:
            self._attr_native_step = ctrl_def.step
        if ctrl_def.unit:
            self._attr_native_unit_of_measurement = ctrl_def.unit
        if ctrl_def.icon:
            self._attr_icon = ctrl_def.icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    @property
    def available(self) -> bool:
        """Keep head-specific controls unavailable when the wrong head is attached."""
        return super().available and control_matches_device(
            self.coordinator, self._device, self._ctrl_def
        )

    @property
    def native_value(self) -> float | None:
        # During cooldown, return optimistic value to prevent flicker
        if (
            self._optimistic_value is not None
            and time.monotonic() - self._command_sent_at < COMMAND_COOLDOWN_SECONDS
        ):
            return self._optimistic_value
        raw = self._get_state_value()
        if raw is None:
            # Device does not report this field back; keep the last sent value
            return self._optimistic_value
        val = float(raw)
        # Volume is reported as 0-1 float, scale to 0-100 for display
        if self._ctrl_def.command_builder == "sound_volume":
            val = int(val * 100)
        return val

    async def async_will_remove_from_hass(self) -> None:
        """Clean up keepalive timer when entity is removed."""
        self._stop_blade_speed_keepalive()

    def _start_blade_speed_keepalive(self) -> None:
        if self._ctrl_def.command_topic != BLADE_SPEED_TOPIC:
            return
        if self._blade_speed_keepalive_unsub is not None:
            return
        self._blade_speed_keepalive_unsub = async_track_time_interval(
            self.hass, self._async_blade_speed_keepalive, BLADE_SPEED_KEEPALIVE_INTERVAL
        )

    def _stop_blade_speed_keepalive(self) -> None:
        if self._blade_speed_keepalive_unsub is None:
            return
        self._blade_speed_keepalive_unsub()
        self._blade_speed_keepalive_unsub = None

    async def _async_blade_speed_keepalive(self, _now) -> None:
        if self._optimistic_value is None:
            self._stop_blade_speed_keepalive()
            return
        try:
            bound = self.coordinator.bound_device(self._device.sn)
            if bound is not None:
                await self.hass.async_add_executor_job(
                    bound.mower.set_blade_speed, int(self._optimistic_value)
                )
            else:
                payload = self._build_payload(self._optimistic_value)
                await self.hass.async_add_executor_job(
                    self.coordinator._client.mqtt_publish_command,
                    self._device.sn,
                    self._device.type_id,
                    self._ctrl_def.command_topic,
                    payload,
                )
        except Exception as exc:
            _LOGGER.error("[number] blade speed keepalive FAILED: %s", exc)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new value to the device."""
        if not control_matches_device(self.coordinator, self._device, self._ctrl_def):
            raise HomeAssistantError(
                f"{self._ctrl_def.name} is unavailable for the current Yarbo head"
            )
        self._optimistic_value = value
        self._command_sent_at = time.monotonic()
        if value == 0:
            # Mirror firmware stop(): cancel timer, send speed=0 once (below), done
            self._stop_blade_speed_keepalive()
        else:
            self._start_blade_speed_keepalive()
        # Volume UI is 0-100, device expects 0-1 float
        device_value = value
        if self._ctrl_def.command_builder == "sound_volume":
            device_value = value / 100.0
        try:
            bound = self.coordinator.bound_device(self._device.sn)
            if bound is not None and await self._dispatch_typed(bound, device_value):
                return
            payload = self._build_payload(device_value)
            await self.hass.async_add_executor_job(
                bound.core.publish_command if bound is not None
                else self.coordinator._client.core.publish_command,
                self._device.sn,
                self._ctrl_def.command_topic,
                payload,
                self._device.type_id,
            )
        except Exception as exc:
            _LOGGER.error("[number] command FAILED: %s", exc)

    async def _dispatch_typed(self, bound, value: float) -> bool:
        """Route to a typed bound method. Returns True if dispatched."""
        topic = self._ctrl_def.command_topic
        if self._ctrl_def.command_builder == "sound_volume":
            current_enable = self._get_sibling_value("StateMSG.enable_sound")
            enable = bool(current_enable) if current_enable is not None else True
            await self.hass.async_add_executor_job(
                bound.core.set_sound_param, enable, round(value, 1)
            )
            return True
        if topic == "mower_target_cmd":
            await self.hass.async_add_executor_job(
                bound.mower.set_blade_height, int(value)
            )
            return True
        if topic == "mower_speed_cmd":
            await self.hass.async_add_executor_job(
                bound.mower.set_blade_speed, int(value)
            )
            return True
        if topic == "cmd_set_chute_angle":
            await self.hass.async_add_executor_job(
                bound.snow_blower.set_chute_angle, int(value)
            )
            return True
        return False

    def _build_payload(self, value: float) -> dict:
        """Build command payload based on command_builder type."""
        builder = self._ctrl_def.command_builder
        if builder == "sound_volume":
            current_enable = self._get_sibling_value("StateMSG.enable_sound")
            enable = bool(current_enable) if current_enable is not None else True
            return {"enable": enable, "vol": round(value, 1), "mode": 0}
        payload = {}
        if self._ctrl_def.command_key:
            payload[self._ctrl_def.command_key] = self._format_command_value(value)
        if self._ctrl_def.extra_payload:
            payload.update(self._ctrl_def.extra_payload)
        return payload

    def _format_command_value(self, value: float) -> float | int:
        """Keep integer-step controls as ints in MQTT payloads."""
        if float(value).is_integer():
            step = self._ctrl_def.step
            if step is None or float(step).is_integer():
                return int(value)
        return value

    def _get_state_value(self):
        if not self.coordinator.data:
            return None
        device_data = self.coordinator.data.get(self._device.sn)
        if device_data is None:
            return None
        from yarbo_robot_sdk.device_helpers import extract_field
        return extract_field(device_data, self._ctrl_def.path)

    def _get_sibling_value(self, field_path: str):
        if not self.coordinator.data:
            return None
        device_data = self.coordinator.data.get(self._device.sn)
        if device_data is None:
            return None
        from yarbo_robot_sdk.device_helpers import extract_field
        return extract_field(device_data, field_path)


class YarboPlanStartPercent(RestoreEntity, NumberEntity):
    """Plan start percent — local-only number entity for Start Plan input."""

    _attr_has_entity_name = True
    _attr_name = "Plan Start Percent"
    _attr_native_min_value = 0
    _attr_native_max_value = 99
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator, device) -> None:
        self._coordinator = coordinator
        self._device = device
        self._attr_unique_id = f"{device.sn}_plan_start_percent"
        self._attr_native_value: float = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    async def async_added_to_hass(self) -> None:
        """Restore previous value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
            except ValueError:
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Store the value locally (no MQTT command)."""
        self._attr_native_value = value
        self.async_write_ha_state()
