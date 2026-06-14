"""Sensor platform for Yarbo integration — configuration-driven."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from yarbo_robot_sdk.device_helpers import convert_local_to_gps, extract_field

from .const import DOMAIN
from .coordinator import YarboDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# keep — intentional: SDK marks these disabled_by_default conservatively; all are
# useful diagnostic sensors that should be on out of the box for this integration.
_FORCE_ENABLED: frozenset[str] = frozenset(
    f"BatteryMSG.temperature{i}" for i in range(1, 7)
) | {
    "BatteryMSG.voltage",
    "BatteryMSG.current",
    "__computed__.charging_power",
    "halow_status.strength",
    "StateMSG.obstacle",
    "RunningStatusMSG.rain_sensor_data",
    "CombinedOdom.x",
    "CombinedOdom.y",
    "CombinedOdom.phi",
    "RTKMSG.sat_num",
}

# Sensor device_classes that represent a numeric measurement
MEASUREMENT_CLASSES = {
    "battery",
    "current",
    "distance",
    "duration",
    "humidity",
    "power",
    "pressure",
    "signal_strength",
    "temperature",
    "voltage",
}

# on_going_planning status code → display text
PLANNING_STATUS_MAP: dict[int, str] = {
    0: "Not Started",
    1: "Cleaning",
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yarbo sensors dynamically from SDK field definitions."""
    from yarbo_robot_sdk import get_field_definitions

    coordinator: YarboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for device in coordinator.devices:
        field_defs = await hass.async_add_executor_job(
            get_field_definitions, device.type_id
        )
        for field_def in field_defs:
            if field_def.entity_type == "sensor":
                entities.append(YarboConfigSensor(coordinator, device, field_def))

    # Add map zone sensors
    from .map_sensor import YarboMapSensor

    for device in coordinator.devices:
        entities.append(YarboMapSensor(coordinator, device))

        # keep — intentional: plan feedback sensors restored; upstream removed these
        # but they are essential for dashboard monitoring of plan execution.
        entities.append(YarboPlanPathSensor(coordinator, device))
        entities.append(YarboCurrentPlanSensor(coordinator, device))
        entities.append(YarboCleanAreaSensor(coordinator, device))
        entities.append(YarboBatteryConsumptionSensor(coordinator, device))
        entities.append(YarboPlanProgressSensor(coordinator, device))
        entities.append(YarboRemainingAreaSensor(coordinator, device))
        entities.append(YarboTimeRemainingSensor(coordinator, device))
        entities.append(YarboElapsedTimeSensor(coordinator, device))
        entities.append(YarboTotalPlanAreaSensor(coordinator, device))
        entities.append(YarboTotalPlanTimeSensor(coordinator, device))

        # keep — intentional: raw telemetry sensors restored from upstream removal (v0.4.8)
        # WheelSpeedMSG, ultrasonic_msg, RunningStatusMSG gyro/chute are not in SDK field defs.
        entities.append(YarboSpeedSensor(coordinator, device))
        entities.append(YarboOdometryLeftSensor(coordinator, device))
        entities.append(YarboOdometryRightSensor(coordinator, device))
        entities.append(YarboOdomConfidenceSensor(coordinator, device))
        entities.append(YarboChuteSensor(coordinator, device))  # Snow Blower head only
        entities.append(YarboProximityLeftSensor(coordinator, device))
        entities.append(YarboProximityCenterSensor(coordinator, device))
        entities.append(YarboProximityRightSensor(coordinator, device))
        entities.append(YarboGyroPitchSensor(coordinator, device))
        entities.append(YarboGyroRollSensor(coordinator, device))

        # Extended raw telemetry — from live MQTT key inventory 2026-06-14
        entities.extend(
            [
                # Body chassis gyro (RunningStatusMSG)
                YarboBodyGyroPitchSensor(coordinator, device),
                YarboBodyGyroRollSensor(coordinator, device),
                YarboBodyGyroYawSensor(coordinator, device),
                YarboBodyAccXSensor(coordinator, device),
                YarboBodyAccYSensor(coordinator, device),
                YarboBodyAccZSensor(coordinator, device),
                YarboBodyAngVelXSensor(coordinator, device),
                YarboBodyAngVelYSensor(coordinator, device),
                YarboBodyAngVelZSensor(coordinator, device),
                # RunningStatusMSG misc
                YarboImpactSensor(coordinator, device),
                YarboPushPodStatusSensor(coordinator, device),
                YarboPushRodPlaceSensor(coordinator, device),
                # EletricMSG
                YarboLeftWheelCurrentSensor(coordinator, device),
                YarboRightWheelCurrentSensor(coordinator, device),
                YarboBrushlessMotorCurrentSensor(coordinator, device),
                YarboPushPodCurrentSensor(coordinator, device),
                YarboChuteSteeringCurrentSensor(
                    coordinator, device
                ),  # snow blower only
                YarboChuteCurrentSensor(coordinator, device),  # snow blower only
                YarboMosTempSensor(coordinator, device),
                YarboMotorNtcTempSensor(coordinator, device),
                # Mower blade motors (mower heads only)
                YarboMiddleBladeCurrentSensor(coordinator, device),
                YarboMiddleBladeRpmSensor(coordinator, device),
                YarboMiddleBladeSpeedSensor(coordinator, device),
                YarboMiddleBladeTempSensor(coordinator, device),
                YarboMiddleBladeTempStatusSensor(coordinator, device),
                YarboMiddleBladeErrSensor(coordinator, device),
                YarboMiddleBladeOverCurrentSensor(coordinator, device),
                YarboLeftBladeCurrentSensor(coordinator, device),
                YarboLeftBladeRpmSensor(coordinator, device),
                YarboLeftBladeSpeedSensor(coordinator, device),
                YarboLeftBladeTempSensor(coordinator, device),
                YarboLeftBladeTempStatusSensor(coordinator, device),
                YarboLeftBladeErrSensor(coordinator, device),
                YarboLeftBladeOverCurrentSensor(coordinator, device),
                YarboRightBladeCurrentSensor(coordinator, device),
                YarboRightBladeRpmSensor(coordinator, device),
                YarboRightBladeSpeedSensor(coordinator, device),
                YarboRightBladeTempSensor(coordinator, device),
                YarboRightBladeTempStatusSensor(coordinator, device),
                YarboRightBladeErrSensor(coordinator, device),
                YarboRightBladeOverCurrentSensor(coordinator, device),
                YarboLiftMotorCurrentSensor(coordinator, device),
                YarboLiftMotorPlaceSensor(coordinator, device),
                YarboRaiseSensorSensor(coordinator, device),
                # Onboard compute health (system_info)
                YarboCpuTemperatureSensor(coordinator, device),
                YarboCpuUsageSensor(coordinator, device),
                YarboCpuFrequencySensor(coordinator, device),
                YarboMemFreeSensor(coordinator, device),
                YarboMemTotalSensor(coordinator, device),
                YarboMemAvailableSensor(coordinator, device),
                YarboDiskAvailableSensor(coordinator, device),
                YarboDiskUsedSensor(coordinator, device),
                # Wireless recharge
                YarboWirelessChargeVoltageSensor(coordinator, device),
                YarboWirelessChargeCurrentSensor(coordinator, device),
                YarboWirelessChargeTempSensor(coordinator, device),
                YarboWirelessChargeStateSensor(coordinator, device),
                # RTKMSG extras
                YarboRtkHeadingSensor(coordinator, device),
                YarboRtkLatitudeSensor(coordinator, device),
                YarboRtkLongitudeSensor(coordinator, device),
                YarboRtkAltitudeSensor(coordinator, device),
                # Hardware/firmware versions
                YarboBodyHardwareVersionSensor(coordinator, device),
                YarboHeadHardwareVersionSensor(coordinator, device),
                YarboRadarHardwareVersionSensor(coordinator, device),
                YarboChassisVersionSensor(coordinator, device),
                YarboPackageVersionSensor(coordinator, device),
                YarboBleVersionSensor(coordinator, device),
                YarboBaseNameSensor(coordinator, device),
                # Flat numeric
                YarboBaseStatusSensor(coordinator, device),
                YarboPositionDeviationSensor(coordinator, device),
                YarboRtcmAgeSensor(coordinator, device),
            ]
        )
    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Raw telemetry sensors — keep: restored from upstream removal (v0.4.8)
# These read directly from coordinator.data[sn] MQTT payloads; the upstream
# config-driven sensor architecture does not expose WheelSpeedMSG,
# ultrasonic_msg, or the RunningStatusMSG gyro/chute fields via SDK field
# definitions, so hand-written classes are required.
# ---------------------------------------------------------------------------

_HEAD_SNOW_BLOWER: tuple[int, ...] = (1,)  # chute angle only on snow blower head
_HEAD_MOWER: tuple[int, ...] = (3, 5)  # blade motor sensors — mower heads only


class _YarboRawSensorBase(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Base for sensors reading directly from coordinator.data[sn]."""

    _attr_has_entity_name = True
    # Subclasses set to a tuple of allowed head_type ints; None means all heads.
    _head_type_required: tuple[int, ...] | None = None
    _unique_id_suffix: str = ""

    def __init__(self, coordinator: YarboDataUpdateCoordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_{self._unique_id_suffix}"

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
            head_type = extract_field(self._data(), "HeadMsg.head_type")
            if head_type is None:
                return False  # head type not yet known — treat as unavailable
            return int(head_type) in self._head_type_required
        return True

    def _data(self) -> dict:
        return (self.coordinator.data or {}).get(self._device.sn) or {}


class YarboSpeedSensor(_YarboRawSensorBase):
    """Average forward speed derived from wheel encoders."""

    _attr_name = "Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "m/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unique_id_suffix = "speed"

    @property
    def native_value(self) -> float | None:
        ws = self._data().get("WheelSpeedMSG") or {}
        left = ws.get("left")
        right = ws.get("right")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        return round((float(left) + float(right)) / 2.0, 3)


class _YarboOdometrySensor(_YarboRawSensorBase):
    """Shared base for left/right wheel odometry sensors."""

    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("WheelSpeedMSG") or {}).get(self._mqtt_key)
        return round(float(val), 1) if isinstance(val, (int, float)) else None


class YarboOdometryLeftSensor(_YarboOdometrySensor):
    """Left wheel odometry — cumulative distance since power-on."""

    _attr_name = "Odometry Left"
    _unique_id_suffix = "odometry_left"
    _mqtt_key = "dist_left"


class YarboOdometryRightSensor(_YarboOdometrySensor):
    """Right wheel odometry — cumulative distance since power-on."""

    _attr_name = "Odometry Right"
    _unique_id_suffix = "odometry_right"
    _mqtt_key = "dist_right"


class YarboOdomConfidenceSensor(_YarboRawSensorBase):
    """Fused odometry / positioning confidence (0–1)."""

    _attr_name = "Positioning Confidence"
    _attr_icon = "mdi:crosshairs"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unique_id_suffix = "odom_confidence"

    @property
    def native_value(self) -> float | None:
        val = self._data().get("combined_odom_confidence")
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboChuteSensor(_YarboRawSensorBase):
    """Snow chute angle — Snow Blower head only."""

    _attr_name = "Chute Angle"
    _attr_icon = "mdi:rotate-right"
    _attr_native_unit_of_measurement = "°"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _head_type_required = _HEAD_SNOW_BLOWER
    _unique_id_suffix = "chute_angle"

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get("chute_angle")
        return float(val) if isinstance(val, (int, float)) else None


class _YarboProximitySensor(_YarboRawSensorBase):
    """Shared base for ultrasonic proximity sensors (9999 = no obstacle)."""

    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("ultrasonic_msg") or {}).get(self._mqtt_key)
        if not isinstance(val, (int, float)) or val >= 9999:
            return None
        return float(val)


class YarboProximityLeftSensor(_YarboProximitySensor):
    """Left front ultrasonic distance."""

    _attr_name = "Proximity Left"
    _unique_id_suffix = "proximity_left"
    _mqtt_key = "lf_dis"


class YarboProximityCenterSensor(_YarboProximitySensor):
    """Center ultrasonic distance."""

    _attr_name = "Proximity Center"
    _unique_id_suffix = "proximity_center"
    _mqtt_key = "mt_dis"


class YarboProximityRightSensor(_YarboProximitySensor):
    """Right front ultrasonic distance."""

    _attr_name = "Proximity Right"
    _unique_id_suffix = "proximity_right"
    _mqtt_key = "rf_dis"


class _YarboGyroSensor(_YarboRawSensorBase):
    """Shared base for head gyroscope sensors (diagnostic, disabled by default)."""

    _attr_native_unit_of_measurement = "°"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboGyroPitchSensor(_YarboGyroSensor):
    """Head attachment gyroscope pitch angle."""

    _attr_name = "Head Gyro Pitch"
    _attr_icon = "mdi:axis-x-rotate-clockwise"
    _unique_id_suffix = "gyro_pitch"
    _mqtt_key = "head_gyro_pitch"


class YarboGyroRollSensor(_YarboGyroSensor):
    """Head attachment gyroscope roll angle."""

    _attr_name = "Head Gyro Roll"
    _attr_icon = "mdi:axis-y-rotate-clockwise"
    _unique_id_suffix = "gyro_roll"
    _mqtt_key = "head_gyro_roll"


# ---------------------------------------------------------------------------
# Extended raw telemetry — derived from live MQTT key inventory 2026-06-14
# All sensors disabled by default except CPU temperature and CPU usage.
# ---------------------------------------------------------------------------


class _YarboRunningStatusSensor(_YarboRawSensorBase):
    """Shared base for RunningStatusMSG scalar sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RunningStatusMSG") or {}).get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


# Body chassis gyro (distinct from head gyro in _YarboGyroSensor)


class YarboBodyGyroPitchSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Gyro Pitch"
    _attr_icon = "mdi:axis-x-rotate-clockwise"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "body_gyro_pitch"
    _mqtt_key = "gyro_pitch"


class YarboBodyGyroRollSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Gyro Roll"
    _attr_icon = "mdi:axis-y-rotate-clockwise"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "body_gyro_roll"
    _mqtt_key = "gyro_roll"


class YarboBodyGyroYawSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Gyro Yaw"
    _attr_icon = "mdi:axis-z-rotate-clockwise"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "body_gyro_yaw"
    _mqtt_key = "gyro_yaw"


class YarboBodyAccXSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Acceleration X"
    _attr_icon = "mdi:axis-x-arrow"
    _attr_native_unit_of_measurement = "m/s²"
    _unique_id_suffix = "body_acc_x"
    _mqtt_key = "gyro_acc_x"


class YarboBodyAccYSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Acceleration Y"
    _attr_icon = "mdi:axis-y-arrow"
    _attr_native_unit_of_measurement = "m/s²"
    _unique_id_suffix = "body_acc_y"
    _mqtt_key = "gyro_acc_y"


class YarboBodyAccZSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Acceleration Z"
    _attr_icon = "mdi:axis-z-arrow"
    _attr_native_unit_of_measurement = "m/s²"
    _unique_id_suffix = "body_acc_z"
    _mqtt_key = "gyro_acc_z"


class YarboBodyAngVelXSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Angular Velocity X"
    _attr_icon = "mdi:rotate-3d-variant"
    _attr_native_unit_of_measurement = "rad/s"
    _unique_id_suffix = "body_ang_vel_x"
    _mqtt_key = "gyro_ang_vel_x"


class YarboBodyAngVelYSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Angular Velocity Y"
    _attr_icon = "mdi:rotate-3d-variant"
    _attr_native_unit_of_measurement = "rad/s"
    _unique_id_suffix = "body_ang_vel_y"
    _mqtt_key = "gyro_ang_vel_y"


class YarboBodyAngVelZSensor(_YarboRunningStatusSensor):
    _attr_name = "Body Angular Velocity Z"
    _attr_icon = "mdi:rotate-3d-variant"
    _attr_native_unit_of_measurement = "rad/s"
    _unique_id_suffix = "body_ang_vel_z"
    _mqtt_key = "gyro_ang_vel_z"


# RunningStatusMSG misc


class YarboImpactSensor(_YarboRunningStatusSensor):
    _attr_name = "Impact Sensor"
    _attr_icon = "mdi:car-brake-alert"
    _unique_id_suffix = "impact_sensor"
    _mqtt_key = "impact_sensor"


class YarboPushPodStatusSensor(_YarboRunningStatusSensor):
    _attr_name = "Push Pod Status"
    _attr_icon = "mdi:piston"
    _unique_id_suffix = "push_pod_status"
    _mqtt_key = "push_pod_status"


class YarboPushRodPlaceSensor(_YarboRunningStatusSensor):
    _attr_name = "Push Rod Place"
    _attr_icon = "mdi:wrench"
    _unique_id_suffix = "push_rod_place"
    _mqtt_key = "push_rod_place"


# ---------------------------------------------------------------------------
# EletricMSG sensors
# ---------------------------------------------------------------------------


class _YarboElectricSensor(_YarboRawSensorBase):
    """Shared base for EletricMSG scalar sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("EletricMSG") or {}).get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboLeftWheelCurrentSensor(_YarboElectricSensor):
    _attr_name = "Left Wheel Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "left_wheel_current"
    _mqtt_key = "lwheel_current"


class YarboRightWheelCurrentSensor(_YarboElectricSensor):
    _attr_name = "Right Wheel Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "right_wheel_current"
    _mqtt_key = "rwheel_current"


class YarboBrushlessMotorCurrentSensor(_YarboElectricSensor):
    _attr_name = "Brushless Motor Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "brushless_motor_current"
    _mqtt_key = "brushless_motor_current"


class YarboPushPodCurrentSensor(_YarboElectricSensor):
    _attr_name = "Push Pod Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "push_pod_current"
    _mqtt_key = "push_pod_current"


class YarboChuteSteeringCurrentSensor(_YarboElectricSensor):
    _attr_name = "Chute Steering Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _head_type_required = _HEAD_SNOW_BLOWER
    _unique_id_suffix = "chute_steering_current"
    _mqtt_key = "chute_streeing_engine_current"  # firmware typo preserved


class YarboChuteCurrentSensor(_YarboElectricSensor):
    _attr_name = "Chute Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _head_type_required = _HEAD_SNOW_BLOWER
    _unique_id_suffix = "chute_current"
    _mqtt_key = "current_chute"


class YarboMosTempSensor(_YarboElectricSensor):
    _attr_name = "MOS Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "mos_temp"
    _mqtt_key = "mos_temp"


class YarboMotorNtcTempSensor(_YarboElectricSensor):
    _attr_name = "Motor NTC Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "motor_ntc_temp"
    _mqtt_key = "ntc_temperature"


# ---------------------------------------------------------------------------
# Mower blade motor sensors (head_info02/03/04 + head_info01 lift extras)
# ---------------------------------------------------------------------------


class _YarboMowerBladeSensor(_YarboRawSensorBase):
    """Shared base for mower blade motor sensors — mower heads only."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _head_type_required = _HEAD_MOWER
    _msg_key: str = ""
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get(self._msg_key) or {}).get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


# Middle blade (mower_head_info02)


class YarboMiddleBladeCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "middle_blade_current"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_current"


class YarboMiddleBladeRpmSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade RPM"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "rpm"
    _unique_id_suffix = "middle_blade_rpm"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_rpm"


class YarboMiddleBladeSpeedSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "%"
    _unique_id_suffix = "middle_blade_speed"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_speed"


class YarboMiddleBladeTempSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "middle_blade_temp"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_temp"


class YarboMiddleBladeTempStatusSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Temp Status"
    _attr_icon = "mdi:thermometer-alert"
    _unique_id_suffix = "middle_blade_temp_status"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_temp_status"


class YarboMiddleBladeErrSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Error"
    _attr_icon = "mdi:alert-circle"
    _unique_id_suffix = "middle_blade_err"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_err"


class YarboMiddleBladeOverCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Middle Blade Overcurrent"
    _attr_icon = "mdi:current-ac"
    _unique_id_suffix = "middle_blade_overcurrent"
    _msg_key = "mower_head_info02"
    _mqtt_key = "middle_blade_motor_over_current_info"


# Left blade (mower_head_info03)


class YarboLeftBladeCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "left_blade_current"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_current"


class YarboLeftBladeRpmSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade RPM"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "rpm"
    _unique_id_suffix = "left_blade_rpm"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_rpm"


class YarboLeftBladeSpeedSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "%"
    _unique_id_suffix = "left_blade_speed"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_speed"


class YarboLeftBladeTempSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "left_blade_temp"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_temp"


class YarboLeftBladeTempStatusSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Temp Status"
    _attr_icon = "mdi:thermometer-alert"
    _unique_id_suffix = "left_blade_temp_status"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_temp_status"


class YarboLeftBladeErrSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Error"
    _attr_icon = "mdi:alert-circle"
    _unique_id_suffix = "left_blade_err"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_err"


class YarboLeftBladeOverCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Left Blade Overcurrent"
    _attr_icon = "mdi:current-ac"
    _unique_id_suffix = "left_blade_overcurrent"
    _msg_key = "mower_head_info03"
    _mqtt_key = "left_blade_motor_over_current_info"


# Right blade (mower_head_info04)


class YarboRightBladeCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "right_blade_current"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_current"


class YarboRightBladeRpmSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade RPM"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "rpm"
    _unique_id_suffix = "right_blade_rpm"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_rpm"


class YarboRightBladeSpeedSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "%"
    _unique_id_suffix = "right_blade_speed"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_speed"


class YarboRightBladeTempSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "right_blade_temp"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_temp"


class YarboRightBladeTempStatusSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Temp Status"
    _attr_icon = "mdi:thermometer-alert"
    _unique_id_suffix = "right_blade_temp_status"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_temp_status"


class YarboRightBladeErrSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Error"
    _attr_icon = "mdi:alert-circle"
    _unique_id_suffix = "right_blade_err"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_err"


class YarboRightBladeOverCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Right Blade Overcurrent"
    _attr_icon = "mdi:current-ac"
    _unique_id_suffix = "right_blade_overcurrent"
    _msg_key = "mower_head_info04"
    _mqtt_key = "right_blade_motor_over_current_info"


# Lift motor (mower_head_info01 extras — already has rain_sensor via SDK)


class YarboLiftMotorCurrentSensor(_YarboMowerBladeSensor):
    _attr_name = "Lift Motor Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "lift_motor_current"
    _msg_key = "mower_head_info01"
    _mqtt_key = "lift_motor_current"


class YarboLiftMotorPlaceSensor(_YarboMowerBladeSensor):
    _attr_name = "Lift Motor Place"
    _attr_icon = "mdi:arrow-up-down"
    _unique_id_suffix = "lift_motor_place"
    _msg_key = "mower_head_info01"
    _mqtt_key = "lift_motor_place"


class YarboRaiseSensorSensor(_YarboMowerBladeSensor):
    _attr_name = "Raise Sensor"
    _attr_icon = "mdi:arrow-up-bold"
    _unique_id_suffix = "raise_sensor"
    _msg_key = "mower_head_info01"
    _mqtt_key = "raise_sensor"


# ---------------------------------------------------------------------------
# system_info sensors (CPU / memory / disk health)
# ---------------------------------------------------------------------------


class _YarboSystemInfoSensor(_YarboRawSensorBase):
    """Shared base for system_info sensors. Keys may contain literal dots."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("system_info") or {}).get(self._mqtt_key)
        return round(float(val), 1) if isinstance(val, (int, float)) else None


class YarboCpuTemperatureSensor(_YarboSystemInfoSensor):
    _attr_name = "CPU Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_entity_registry_enabled_default = True
    _unique_id_suffix = "cpu_temperature"
    _mqtt_key = "cpu.Temperature"


class YarboCpuUsageSensor(_YarboSystemInfoSensor):
    _attr_name = "CPU Usage"
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "%"
    _attr_entity_registry_enabled_default = True
    _unique_id_suffix = "cpu_usage"
    _mqtt_key = "cpu.Usage"


class YarboCpuFrequencySensor(_YarboSystemInfoSensor):
    _attr_name = "CPU Frequency"
    _attr_icon = "mdi:sine-wave"
    _attr_native_unit_of_measurement = "MHz"
    _unique_id_suffix = "cpu_frequency"
    _mqtt_key = "cpu.Frequency"


class YarboMemFreeSensor(_YarboSystemInfoSensor):
    _attr_name = "Memory Free"
    _attr_icon = "mdi:memory"
    _attr_native_unit_of_measurement = "kB"
    _unique_id_suffix = "mem_free"
    _mqtt_key = "mem.MemFree"


class YarboMemTotalSensor(_YarboSystemInfoSensor):
    _attr_name = "Memory Total"
    _attr_icon = "mdi:memory"
    _attr_native_unit_of_measurement = "kB"
    _unique_id_suffix = "mem_total"
    _mqtt_key = "mem.MemTotal"


class YarboMemAvailableSensor(_YarboSystemInfoSensor):
    _attr_name = "Memory Available"
    _attr_icon = "mdi:memory"
    _attr_native_unit_of_measurement = "kB"
    _unique_id_suffix = "mem_available"
    _mqtt_key = "mem.MemAvailable"


class YarboDiskAvailableSensor(_YarboSystemInfoSensor):
    _attr_name = "Disk Available"
    _attr_icon = "mdi:harddisk"
    _attr_native_unit_of_measurement = "B"
    _unique_id_suffix = "disk_available"
    _mqtt_key = "userdata.disk.availableSize"


class YarboDiskUsedSensor(_YarboSystemInfoSensor):
    _attr_name = "Disk Used"
    _attr_icon = "mdi:harddisk"
    _attr_native_unit_of_measurement = "B"
    _unique_id_suffix = "disk_used"
    _mqtt_key = "userdata.disk.usedSize"


# ---------------------------------------------------------------------------
# Wireless recharge sensors
# ---------------------------------------------------------------------------


class _YarboWirelessRechargeSensor(_YarboRawSensorBase):
    """Shared base for wireless_recharge sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("wireless_recharge") or {}).get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboWirelessChargeVoltageSensor(_YarboWirelessRechargeSensor):
    _attr_name = "Wireless Charge Voltage"
    _attr_icon = "mdi:flash"
    _attr_native_unit_of_measurement = "V"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _unique_id_suffix = "wireless_charge_voltage"
    _mqtt_key = "output_voltage"


class YarboWirelessChargeCurrentSensor(_YarboWirelessRechargeSensor):
    _attr_name = "Wireless Charge Current"
    _attr_icon = "mdi:current-dc"
    _attr_native_unit_of_measurement = "A"
    _attr_device_class = SensorDeviceClass.CURRENT
    _unique_id_suffix = "wireless_charge_current"
    _mqtt_key = "output_current"


class YarboWirelessChargeTempSensor(_YarboWirelessRechargeSensor):
    _attr_name = "Wireless Charge Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _unique_id_suffix = "wireless_charge_temp"
    _mqtt_key = "temperature"


class YarboWirelessChargeStateSensor(_YarboWirelessRechargeSensor):
    _attr_name = "Wireless Charge State"
    _attr_icon = "mdi:battery-charging-wireless"
    _unique_id_suffix = "wireless_charge_state"
    _mqtt_key = "state"


# ---------------------------------------------------------------------------
# RTKMSG extra sensors (beyond status + sat_num covered by SDK)
# ---------------------------------------------------------------------------


class _YarboRTKSensor(_YarboRawSensorBase):
    """Shared base for RTKMSG scalar sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = (self._data().get("RTKMSG") or {}).get(self._mqtt_key)
        return round(float(val), 6) if isinstance(val, (int, float)) else None


class YarboRtkHeadingSensor(_YarboRTKSensor):
    _attr_name = "RTK Heading"
    _attr_icon = "mdi:compass-rose"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "rtk_heading"
    _mqtt_key = "heading"


class YarboRtkLatitudeSensor(_YarboRTKSensor):
    _attr_name = "RTK Latitude"
    _attr_icon = "mdi:latitude"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "rtk_latitude"
    _mqtt_key = "lan"  # firmware key name (typo for "lat")


class YarboRtkLongitudeSensor(_YarboRTKSensor):
    _attr_name = "RTK Longitude"
    _attr_icon = "mdi:longitude"
    _attr_native_unit_of_measurement = "°"
    _unique_id_suffix = "rtk_longitude"
    _mqtt_key = "lon"


class YarboRtkAltitudeSensor(_YarboRTKSensor):
    _attr_name = "RTK Altitude"
    _attr_icon = "mdi:elevation-rise"
    _attr_native_unit_of_measurement = "m"
    _unique_id_suffix = "rtk_altitude"
    _mqtt_key = "hgt"


# ---------------------------------------------------------------------------
# Hardware/firmware version string sensors
# ---------------------------------------------------------------------------


class _YarboStringKeySensor(_YarboRawSensorBase):
    """Shared base for string-valued sensors."""

    _attr_entity_registry_enabled_default = False
    _msg_key: str = ""
    _mqtt_key: str = ""

    @property
    def native_value(self) -> str | None:
        if self._msg_key:
            val = (self._data().get(self._msg_key) or {}).get(self._mqtt_key)
        else:
            val = self._data().get(self._mqtt_key)
        return str(val) if val is not None else None


class YarboBodyHardwareVersionSensor(_YarboStringKeySensor):
    _attr_name = "Body Hardware Version"
    _attr_icon = "mdi:chip"
    _unique_id_suffix = "body_hardware_version"
    _msg_key = "hardware_version"
    _mqtt_key = "body_version"


class YarboHeadHardwareVersionSensor(_YarboStringKeySensor):
    _attr_name = "Head Hardware Version"
    _attr_icon = "mdi:chip"
    _unique_id_suffix = "head_hardware_version"
    _msg_key = "hardware_version"
    _mqtt_key = "head_version"


class YarboRadarHardwareVersionSensor(_YarboStringKeySensor):
    _attr_name = "Radar Hardware Version"
    _attr_icon = "mdi:chip"
    _unique_id_suffix = "radar_hardware_version"
    _msg_key = "hardware_version"
    _mqtt_key = "radar_version"


class YarboChassisVersionSensor(_YarboStringKeySensor):
    _attr_name = "Chassis Firmware Version"
    _attr_icon = "mdi:chip"
    _unique_id_suffix = "chassis_version"
    _msg_key = "chassis_version_msg"
    _mqtt_key = "firmware_version"


class YarboPackageVersionSensor(_YarboStringKeySensor):
    _attr_name = "Firmware Package Version"
    _attr_icon = "mdi:tag"
    _unique_id_suffix = "firmware_package_version"
    _msg_key = ""
    _mqtt_key = "version"


class YarboBleVersionSensor(_YarboStringKeySensor):
    _attr_name = "BLE Version"
    _attr_icon = "mdi:bluetooth"
    _unique_id_suffix = "ble_version"
    _msg_key = ""
    _mqtt_key = "ble_version"


class YarboBaseNameSensor(_YarboStringKeySensor):
    _attr_name = "Base Station Name"
    _attr_icon = "mdi:home-map-marker"
    _unique_id_suffix = "base_name"
    _msg_key = ""
    _mqtt_key = "base_name"


# ---------------------------------------------------------------------------
# Flat top-level numeric sensors
# ---------------------------------------------------------------------------


class _YarboFlatNumericSensor(_YarboRawSensorBase):
    """Shared base for flat top-level numeric sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False
    _mqtt_key: str = ""

    @property
    def native_value(self) -> float | None:
        val = self._data().get(self._mqtt_key)
        return round(float(val), 3) if isinstance(val, (int, float)) else None


class YarboBaseStatusSensor(_YarboFlatNumericSensor):
    _attr_name = "Base Station Status"
    _attr_icon = "mdi:home-map-marker"
    _unique_id_suffix = "base_status"
    _mqtt_key = "base_status"


class YarboPositionDeviationSensor(_YarboFlatNumericSensor):
    _attr_name = "Position Deviation"
    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = "m"
    _unique_id_suffix = "position_deviation"
    _mqtt_key = "pos_devia_dis"


class YarboRtcmAgeSensor(_YarboFlatNumericSensor):
    _attr_name = "RTCM Correction Age"
    _attr_icon = "mdi:satellite-uplink"
    _attr_native_unit_of_measurement = "s"
    _unique_id_suffix = "rtcm_age"
    _mqtt_key = "rtcm_age"


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
        self._attr_entity_registry_enabled_default = (
            True if field_def.path in _FORCE_ENABLED else field_def.enabled_by_default
        )

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

        # HA rejects non-numeric states (e.g. firmware sending "") on sensors
        # whose device_class/unit implies a number, so coerce raw values.
        self._numeric = bool(
            not field_def.value_map
            and (field_def.unit or field_def.device_class in MEASUREMENT_CLASSES)
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
        if self._numeric:
            return self._as_number(raw)
        return raw

    @staticmethod
    def _as_number(value):
        """Coerce a raw value to a number, or None if it isn't one."""
        if isinstance(value, (int, float)):
            return value
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return int(num) if num.is_integer() else num

    def _extract_custom(self):
        """Handle fields with custom_extractor logic."""
        data = self._get_device_data()
        if data is None:
            return None
        if self._field_def.custom_extractor == "network_priority":
            from yarbo_robot_sdk.device_helpers import (
                extract_active_network,
                extract_field,
            )

            route_priority = extract_field(data, self._field_def.path)
            return extract_active_network(route_priority)
        if self._field_def.custom_extractor == "battery_capacity":
            from yarbo_robot_sdk.device_helpers import extract_field

            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            # Firmware reports capacity topping out at 95; rescale the top of
            # the range so a full pack reads 100% (90→90, 91→92, … 95→100).
            val = int(round(float(raw)))
            if val <= 90:
                return val
            if val >= 95:
                return 100
            return 90 + (val - 90) * 2
        if self._field_def.custom_extractor == "volume_scale":
            from yarbo_robot_sdk.device_helpers import extract_field

            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            return int(float(raw) * 100)
        if self._field_def.custom_extractor == "charging_power":
            from yarbo_robot_sdk.device_helpers import extract_field

            # TODO: Replace this computed fallback if firmware starts publishing
            # a real charging power field.
            voltage = extract_field(data, "BatteryMSG.voltage")
            current = extract_field(data, "BatteryMSG.current")
            if voltage is None or current is None:
                return None
            voltage = float(voltage)
            current = float(current)
            if abs(voltage) > 1000:
                voltage = voltage / 1000
            if abs(current) > 1000:
                current = current / 1000
            return round(voltage * current, 2)
        if self._field_def.custom_extractor == "rtk_signal":
            from yarbo_robot_sdk.device_helpers import extract_field

            raw = extract_field(data, self._field_def.path)
            # APP logic: 4=Strong, 5=Medium, everything else=Weak
            raw_int = int(raw) if raw is not None else None
            if raw_int == 4:
                return "Strong"
            if raw_int == 5:
                return "Medium"
            return "Weak"
        if self._field_def.custom_extractor == "planning_status":
            from yarbo_robot_sdk.device_helpers import extract_field

            raw = extract_field(data, self._field_def.path)
            if raw is None:
                return None
            code = int(raw)
            if code in PLANNING_STATUS_MAP:
                return PLANNING_STATUS_MAP[code]
            return "Error" if code < 0 else None
        if self._field_def.custom_extractor == "recharging_status":
            from yarbo_robot_sdk.device_helpers import extract_field

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
        from yarbo_robot_sdk.device_helpers import extract_field

        return extract_field(data, field_path)

    def _get_device_data(self) -> dict | None:
        if self.coordinator.data and self._device.sn in self.coordinator.data:
            return self.coordinator.data[self._device.sn]
        return None


# ---------------------------------------------------------------------------
# Plan feedback sensors — keep: restored from upstream removal
# All read from coordinator.plan_feedback[sn] (plan_feedback MQTT topic)
# ---------------------------------------------------------------------------


def _plan_device_info(device) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device.sn)},
        name=device.name,
        manufacturer="Yarbo",
        model=device.model,
        serial_number=device.sn,
    )


class YarboCurrentPlanSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Name of the currently running plan (from plan_feedback areaIds match)."""

    _attr_has_entity_name = True
    _attr_name = "Current Plan"
    _attr_icon = "mdi:clipboard-play-outline"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_current_plan"

    @property
    def device_info(self) -> DeviceInfo:
        return _plan_device_info(self._device)

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
    """Actual cleaned area in the current run (m²)."""

    _attr_has_entity_name = True
    _attr_name = "Completed Plan Area"
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_clean_area"

    @property
    def device_info(self) -> DeviceInfo:
        return _plan_device_info(self._device)

    @property
    def native_value(self) -> float | None:
        val = (self.coordinator.plan_feedback.get(self._device.sn) or {}).get(
            "actualCleanArea"
        )
        return round(float(val), 2) if val is not None else None


class YarboBatteryConsumptionSensor(
    CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity
):
    """Battery consumed during the current run (%)."""

    _attr_has_entity_name = True
    _attr_name = "Plan Battery Consumption"
    _attr_icon = "mdi:battery-minus"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_battery_consumption"

    @property
    def device_info(self) -> DeviceInfo:
        return _plan_device_info(self._device)

    @property
    def native_value(self) -> float | None:
        val = (self.coordinator.plan_feedback.get(self._device.sn) or {}).get(
            "battery_consumption"
        )
        return float(val) if val is not None else None


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
        return _plan_device_info(self._device)

    def _pf(self) -> dict:
        return self.coordinator.plan_feedback.get(self._device.sn) or {}


class YarboPlanProgressSensor(_YarboPlanFeedbackBase):
    """Plan completion percentage."""

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
    """Remaining area to clean in current run (m²)."""

    _attr_name = "Remaining Plan Area"
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
    """Estimated time remaining in current plan (seconds)."""

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
        val = self._pf().get("leftTime")
        return round(max(float(val), 0), 0) if val is not None else None


class YarboElapsedTimeSensor(_YarboPlanFeedbackBase):
    """Elapsed time in current plan run (seconds)."""

    _attr_name = "Plan Elapsed Time"
    _attr_icon = "mdi:timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_elapsed_time"

    @property
    def native_value(self) -> float | None:
        val = self._pf().get("duration")
        return round(float(val), 0) if val is not None else None


class YarboTotalPlanAreaSensor(_YarboPlanFeedbackBase):
    """Total area of the current plan (m²)."""

    _attr_name = "Total Plan Area"
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.sn}_total_plan_area"

    @property
    def native_value(self) -> float | None:
        val = self._pf().get("totalCleanArea")
        return round(float(val), 2) if val is not None else None


class YarboTotalPlanTimeSensor(_YarboPlanFeedbackBase):
    """Estimated total time for the current plan (seconds)."""

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
        val = self._pf().get("totalTime")
        return round(float(val), 0) if val is not None else None


class YarboPlanPathSensor(CoordinatorEntity[YarboDataUpdateCoordinator], SensorEntity):
    """Live mowing path GeoJSON for the current plan run.

    State = number of path segments received.
    Attribute 'geojson' = GeoJSON FeatureCollection (LineString per segment).
    Disabled by default — large attribute; exclude from recorder to avoid 16 KB warning.
    """

    _attr_has_entity_name = True
    _attr_name = "Plan Path"
    _attr_icon = "mdi:map-marker-path"
    _attr_entity_registry_enabled_default = False  # keep — large attr, opt-in only

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.sn}_plan_path"

    @property
    def device_info(self) -> DeviceInfo:
        return _plan_device_info(self._device)

    @property
    def native_value(self) -> int | None:
        segments = (self.coordinator.plan_feedback.get(self._device.sn) or {}).get(
            "cleanPathProgress"
        ) or []
        return len(segments) if segments else None

    @property
    def extra_state_attributes(self) -> dict:
        pf = self.coordinator.plan_feedback.get(self._device.sn) or {}
        segments = pf.get("cleanPathProgress") or []
        if not segments:
            return {}
        gps_ref = self.coordinator.gps_refs.get(self._device.sn) or {}
        ref = gps_ref.get("ref") or {}
        ref_lat = ref.get("latitude")
        ref_lon = ref.get("longitude")
        if ref_lat is None or ref_lon is None:
            return {}
        try:
            features = []
            for seg in segments:
                pts = seg.get("path") or []
                if len(pts) < 2:
                    continue
                coords = []
                for pt in pts:
                    try:
                        lat, lon = convert_local_to_gps(
                            ref_lat,
                            ref_lon,
                            float(pt.get("x", 0)),
                            float(pt.get("y", 0)),
                        )
                        coords.append([round(lon, 7), round(lat, 7)])
                    except Exception:  # noqa: BLE001
                        pass
                if len(coords) >= 2:
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": coords},
                            "properties": {
                                "area_id": seg.get("id"),
                                "clean_index": seg.get("clean_index"),
                                "clean_times": seg.get("clean_times"),
                            },
                        }
                    )
            if features:
                return {"geojson": {"type": "FeatureCollection", "features": features}}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("plan_path geojson build failed: %s", err)
        return {}
