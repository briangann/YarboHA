"""Sensor platform for Yarbo integration — configuration-driven."""

from __future__ import annotations

from yarbo_robot_sdk import get_field_definitions
from yarbo_robot_sdk.device_helpers import extract_active_network, extract_field

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YarboDataUpdateCoordinator
from .map_sensor import YarboMapSensor

# Sensor device_classes that represent a numeric measurement
MEASUREMENT_CLASSES = {"battery", "temperature", "humidity", "distance", "pressure"}

# on_going_planning status code → display text
# Status 1 ("actively working") is overridden at runtime based on head type.
PLANNING_STATUS_MAP: dict[int, str] = {
    0: "Not Started",
    1: "Working",  # overridden by _PLANNING_ACTIVE_VERB at runtime
    2: "Calculating Route",
    3: "Heading to Area",
    5: "Completed",
    11: "Waypoint Navigation",
    12: "Waypoint Complete",
    -2: "Error: Create Plan History Failed (WP002)",
    -10: "Error: Plan Not Found (WP003)",
    -11: "Error: Failed to Read Plan (WP004)",
    -12: "Error: Failed to Calculate Route (WP005)",
    -20: "Error: Outside Mapped Area (WP006)",
    -21: "Error: Area Data Error (WP007)",
    -22: "Error: Route Data Error (WP008)",
    -23: "Error: In No-Go Zone",
    -24: "Error: Low Battery",
    -26: "Error: Module Position Failure (WP012)",
    -30: "Error: Location Data Exception (WP013)",
    -31: "Error: Docking Station Exception (WP014)",
    -40: "Error: Obstacle Mark Failed",
    -42: "Error: Out of Boundary",
    -43: "Error: Unable to Navigate Obstacle (WP016)",
    -44: "Error: Exceeded Boundary (WP017)",
    -47: "Error: Out of Boundary >1.5m",
    -88: "Error: In No-Go Zone",
    -92: "Error: Out of Boundary (WP025)",
}

# on_going_recharging status code → display text
RECHARGING_STATUS_MAP: dict[int, str] = {
    0: "Not Started",
    1: "Returning on Path",
    2: "Returning in Area",
    3: "Repositioning",
    4: "Charging",
    99: "Verifying",
    -2: "Error: Server Error",
    -3: "Error: Direction Uninitialized",
    -4: "Error: Docking Station Uninitialized",
    -5: "Error: Recharge Failed (REC005)",
    -6: "Error: Failed to Park",
    -8: "Error: Docking Connection Failed",
    -9: "Error: Stuck",
    -20: "Error: Outside Mapped Area",
}

# Head type → active-work verb (used when on_going_planning == 1)
_PLANNING_ACTIVE_VERB: dict[int, str] = {
    0: "Running",  # No head
    1: "Blowing Snow",  # Snow Blower
    2: "Blowing",  # Blower
    3: "Mowing",  # Mower
    4: "Working",  # Smart Cover
    5: "Mowing",  # Mower Pro
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo sensors dynamically from SDK field definitions."""

    coordinator: YarboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for device in coordinator.devices:
        field_defs = await hass.async_add_executor_job(
            get_field_definitions, device.type_id
        )
        for field_def in field_defs:
            if field_def.entity_type == "sensor":
                entities.append(YarboConfigSensor(coordinator, device, field_def))

    # Add map zone sensors, plan feedback sensors, and raw telemetry sensors
    for device in coordinator.devices:
        entities.append(YarboMapSensor(coordinator, device))
        entities.append(YarboCurrentPlanSensor(coordinator, device))
        entities.append(YarboCleanAreaSensor(coordinator, device))
        entities.append(YarboBatteryConsumptionSensor(coordinator, device))
        entities.append(YarboPlanProgressSensor(coordinator, device))
        entities.append(YarboRemainingAreaSensor(coordinator, device))
        entities.append(YarboTimeRemainingSensor(coordinator, device))
        entities.append(YarboElapsedTimeSensor(coordinator, device))
        entities.append(YarboTotalPlanAreaSensor(coordinator, device))
        entities.append(YarboTotalPlanTimeSensor(coordinator, device))
        # Raw telemetry
        entities.append(YarboSpeedSensor(coordinator, device))
        entities.append(YarboOdometryLeftSensor(coordinator, device))
        entities.append(YarboOdometryRightSensor(coordinator, device))
        entities.append(YarboOdomConfidenceSensor(coordinator, device))
        entities.append(YarboRainSensor(coordinator, device))
        entities.append(YarboChuteSensor(coordinator, device))  # Snow Blower only
        entities.append(YarboProximityLeftSensor(coordinator, device))
        entities.append(YarboProximityCenterSensor(coordinator, device))
        entities.append(YarboProximityRightSensor(coordinator, device))
        entities.append(YarboGyroPitchSensor(coordinator, device))
        entities.append(YarboGyroRollSensor(coordinator, device))

    async_add_entities(entities)


class YarboConfigSensor(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Configuration-driven sensor — one class for all sensor fields."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, field_def) -> None:
        super().__init__(coordinator)
        self._device = device
        self._field_def = field_def

        # Unique ID from SN + normalized path
        path_key = field_def.path.replace(".", "_").replace("__", "").lower()
        self._attr_unique_id = f"{device.sn}_{path_key}"
        self._attr_name = field_def.name
        self._attr_entity_registry_enabled_default = field_def.enabled_by_default

        # Device class
        if field_def.value_map:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(dict.fromkeys(field_def.value_map.values()))
        elif field_def.device_class:
            try:
                self._attr_device_class = SensorDeviceClass(field_def.device_class)
            except ValueError:
                pass

        # State class for numeric measurements
        if field_def.device_class in MEASUREMENT_CLASSES and not field_def.value_map:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Unit and icon
        if field_def.unit:
            self._attr_native_unit_of_measurement = field_def.unit
        if field_def.icon:
            self._attr_icon = field_def.icon

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
    def native_value(self):
        # Special extraction for custom_extractor fields (e.g. network_priority)
        if self._field_def.custom_extractor:
            return self._extract_custom()
        raw = self._extract(self._field_def.path)
        if raw is None:
            return None
        if self._field_def.value_map:
            mapped = self._field_def.value_map.get(str(raw))
            if mapped is not None:
                return mapped
            # For numeric values, check if a negative fallback exists (e.g. all negatives → "Error")
            if isinstance(raw, (int, float)) and raw < 0:
                return self._field_def.value_map.get("-1")
            return None
        return raw

    def _extract_custom(self):
        """Handle fields with custom_extractor logic."""
        data = self._get_device_data()
        if data is None:
            return None
        if self._field_def.custom_extractor == "network_priority":
            route_priority = extract_field(data, self._field_def.path)
            return extract_active_network(route_priority)
        if self._field_def.custom_extractor == "volume_scale":
            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            return int(float(raw) * 100)
        if self._field_def.custom_extractor == "rtk_signal":
            raw = extract_field(data, self._field_def.path)
            # APP logic: 4=Strong, 5=Medium, everything else=Weak
            raw_int = int(raw) if raw is not None else None
            if raw_int == 4:
                return "Strong"
            if raw_int == 5:
                return "Medium"
            return "Weak"
        if self._field_def.custom_extractor == "planning_status":
            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            code = int(raw)
            if code == 1:
                # "Actively working" — use head-type-specific verb
                head_type = extract_field(data, "HeadMsg.head_type")
                try:
                    return _PLANNING_ACTIVE_VERB.get(int(head_type), "Working")
                except (TypeError, ValueError):
                    return "Working"
            if code in PLANNING_STATUS_MAP:
                return PLANNING_STATUS_MAP[code]
            return "Error" if code < 0 else None
        if self._field_def.custom_extractor == "recharging_status":
            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            code = int(raw)
            if code in RECHARGING_STATUS_MAP:
                return RECHARGING_STATUS_MAP[code]
            return "Error" if code < 0 else None
        return None

    def _extract(self, field_path: str):
        """Extract a field value from MQTT data."""
        data = self._get_device_data()
        if data is None:
            return None

        return extract_field(data, field_path)

    def _get_device_data(self) -> dict | None:
        if self.coordinator.data and self._device.sn in self.coordinator.data:
            return self.coordinator.data[self._device.sn]
        return None


class YarboCurrentPlanSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Sensor showing the name of the currently running plan."""

    _attr_has_entity_name = True
    _attr_name = "Current Plan"
    _attr_icon = "mdi:clipboard-play-outline"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_current_plan"

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
    def native_value(self) -> str | None:
        pf = self.coordinator.plan_feedback.get(self._device.sn) or {}
        running_area_ids = set(pf.get("areaIds") or [])
        if not running_area_ids:
            return None
        for plan in self.coordinator.plan_data.get(self._device.sn, []):
            if set(plan.get("areaIds") or []) == running_area_ids:
                return plan.get("name")
        return None


class YarboCleanAreaSensor(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Sensor showing the actual cleaned area in the current run."""

    _attr_has_entity_name = True
    _attr_name = "Clean Area"
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_clean_area"

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
    def native_value(self) -> float | None:
        pf = self.coordinator.plan_feedback.get(self._device.sn) or {}
        val = pf.get("actualCleanArea")
        if val is None:
            return None
        return round(float(val), 2)


class YarboBatteryConsumptionSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Sensor showing battery consumed during the current run."""

    _attr_has_entity_name = True
    _attr_name = "Battery Consumption"
    _attr_icon = "mdi:battery-minus"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_battery_consumption"

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
    def native_value(self) -> float | None:
        pf = self.coordinator.plan_feedback.get(self._device.sn) or {}
        val = pf.get("battery_consumption")
        if val is None:
            return None
        return float(val)


class _YarboPlanFeedbackBase(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Shared base for sensors derived from plan_feedback."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.sn)},
            name=self._device.name,
            manufacturer="Yarbo",
            model=self._device.model,
            serial_number=self._device.sn,
        )

    def _pf(self) -> dict:
        return self.coordinator.plan_feedback.get(self._device.sn) or {}


class YarboPlanProgressSensor(_YarboPlanFeedbackBase):
    """Sensor showing plan completion as a percentage."""

    _attr_name = "Plan Progress"
    _attr_icon = "mdi:progress-clock"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_plan_progress"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        actual = pf.get("actualCleanArea")
        total = pf.get("totalCleanArea")
        if actual is None or not total:
            return None
        return round(min(float(actual) / float(total) * 100, 100), 1)


class YarboRemainingAreaSensor(_YarboPlanFeedbackBase):
    """Sensor showing remaining area to clean in current run."""

    _attr_name = "Remaining Area"
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_remaining_area"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        actual = pf.get("actualCleanArea")
        total = pf.get("totalCleanArea")
        if actual is None or total is None:
            return None
        return round(max(float(total) - float(actual), 0), 2)


class YarboTimeRemainingSensor(_YarboPlanFeedbackBase):
    """Sensor showing estimated time remaining in current plan."""

    _attr_name = "Estimated Time Remaining"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_time_remaining"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        val = pf.get("leftTime")
        if val is None:
            return None
        return round(max(float(val), 0), 0)


class YarboElapsedTimeSensor(_YarboPlanFeedbackBase):
    """Sensor showing elapsed time in current plan run."""

    _attr_name = "Elapsed Time"
    _attr_icon = "mdi:timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_elapsed_time"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        val = pf.get("duration")
        if val is None:
            return None
        return round(float(val), 0)


class YarboTotalPlanAreaSensor(_YarboPlanFeedbackBase):
    """Sensor showing total area of the current plan."""

    _attr_name = "Total Plan Area"
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_total_plan_area"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        val = pf.get("totalCleanArea")
        if val is None:
            return None
        return round(float(val), 2)


class YarboTotalPlanTimeSensor(_YarboPlanFeedbackBase):
    """Sensor showing estimated total time for the current plan."""

    _attr_name = "Total Plan Time"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_total_plan_time"

    @property
    def native_value(self) -> float | None:
        pf = self._pf()
        val = pf.get("totalTime")
        if val is None:
            return None
        return round(float(val), 0)


# ---------------------------------------------------------------------------
# Raw telemetry sensors
# ---------------------------------------------------------------------------
# Head type constants
_HEAD_SNOW_BLOWER = (1,)  # Only snow blower head has a chute


class _YarboRawSensorBase(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Base for sensors reading directly from coordinator.data[sn]."""

    _attr_has_entity_name = True
    # Subclasses may set to a tuple of allowed head_type ints; None = all.
    _head_type_required: tuple[int, ...] | None = None

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device

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
        if not super().available:
            return False
        if self._head_type_required is not None:
            data = (self.coordinator.data or {}).get(self._device.sn) or {}
            head_type = extract_field(data, "HeadMsg.head_type")
            if head_type is not None:
                # Default to available when head_type not yet received (device may be a snow blower).
                try:
                    return int(head_type) in self._head_type_required
                except (ValueError, TypeError):
                    return False
        return True

    def _data(self) -> dict:
        return (self.coordinator.data or {}).get(self._device.sn) or {}


class YarboSpeedSensor(_YarboRawSensorBase):
    """Average forward speed derived from wheel encoders."""

    _attr_name = "Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "m/s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_speed"

    @property
    def native_value(self) -> float | None:
        ws = self._data().get("WheelSpeedMSG") or {}
        left = ws.get("left")
        right = ws.get("right")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        return round((float(left) + float(right)) / 2.0, 3)


class YarboOdometryLeftSensor(_YarboRawSensorBase):
    """Left wheel odometry distance."""

    _attr_name = "Odometry Left"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_odometry_left"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("WheelSpeedMSG") or {}).get("dist_left")
        return round(float(val), 1) if isinstance(val, (int, float)) else None


class YarboOdometryRightSensor(_YarboRawSensorBase):
    """Right wheel odometry distance."""

    _attr_name = "Odometry Right"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_odometry_right"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("WheelSpeedMSG") or {}).get("dist_right")
        return round(float(val), 1) if isinstance(val, (int, float)) else None


class YarboOdomConfidenceSensor(_YarboRawSensorBase):
    """Fused odometry / positioning confidence (0–1)."""

    _attr_name = "Positioning Confidence"
    _attr_icon = "mdi:crosshairs"
    _attr_native_unit_of_measurement = None
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_odom_confidence"

    @property
    def native_value(self) -> float | None:
        val = self._data().get("combined_odom_confidence")
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboRainSensor(_YarboRawSensorBase):
    """Rain sensor raw reading."""

    _attr_name = "Rain Sensor"
    _attr_icon = "mdi:weather-rainy"
    _attr_native_unit_of_measurement = None
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_rain_sensor"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get("rain_sensor_data")
        return float(val) if isinstance(val, (int, float)) else None


class YarboChuteSensor(_YarboRawSensorBase):
    """Snow chute angle — Snow Blower head only."""

    _attr_name = "Chute Angle"
    _attr_icon = "mdi:rotate-right"
    _attr_native_unit_of_measurement = "°"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _head_type_required = _HEAD_SNOW_BLOWER

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_chute_angle"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get("chute_angle")
        return float(val) if isinstance(val, (int, float)) else None


class YarboProximityLeftSensor(_YarboRawSensorBase):
    """Left front ultrasonic distance (9999 = no obstacle)."""

    _attr_name = "Proximity Left"
    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_proximity_left"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("ultrasonic_msg") or {}).get("lf_dis")
        return float(val) if isinstance(val, (int, float)) else None


class YarboProximityCenterSensor(_YarboRawSensorBase):
    """Center ultrasonic distance (9999 = no obstacle)."""

    _attr_name = "Proximity Center"
    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_proximity_center"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("ultrasonic_msg") or {}).get("mt_dis")
        return float(val) if isinstance(val, (int, float)) else None


class YarboProximityRightSensor(_YarboRawSensorBase):
    """Right front ultrasonic distance (9999 = no obstacle)."""

    _attr_name = "Proximity Right"
    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_proximity_right"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("ultrasonic_msg") or {}).get("rf_dis")
        return float(val) if isinstance(val, (int, float)) else None


class YarboGyroPitchSensor(_YarboRawSensorBase):
    """Head attachment gyroscope pitch angle."""

    _attr_name = "Head Gyro Pitch"
    _attr_icon = "mdi:axis-x-rotate-clockwise"
    _attr_native_unit_of_measurement = "°"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False  # Diagnostic — disabled by default

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_gyro_pitch"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get("head_gyro_pitch")
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboGyroRollSensor(_YarboRawSensorBase):
    """Head attachment gyroscope roll angle."""

    _attr_name = "Head Gyro Roll"
    _attr_icon = "mdi:axis-y-rotate-clockwise"
    _attr_native_unit_of_measurement = "°"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False  # Diagnostic — disabled by default

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_gyro_roll"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get("head_gyro_roll")
        return round(float(val), 3) if isinstance(val, (int, float)) else None
