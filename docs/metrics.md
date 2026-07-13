# Yarbo — Entity & Metric Reference

This file is the metric map for the integration. It lists the exposed entities, their raw MQTT or REST source, the displayed unit, and any normalization or suppression rule that affects the value users see.

All metric data arrives via MQTT push or is derived directly from MQTT push. There is no polling.

---

## Quick normalization rules

- `battery_capacity` rescales the firmware cap of 95 to 100.
- `charging_power` is computed from `BatteryMSG.voltage × BatteryMSG.current` and drops values outside `±800 W`.
- `volume_scale` multiplies device `0–1` volume to `0–100`.
- `Wireless Charge Voltage` and `Wireless Charge Current` divide by `1000` when the raw magnitude is greater than `1000`.
- Left/right track current and power report `0` when `Speed == 0` and `StateMSG.activity == "Not Started"`.
- Left/right blade current and power report `0` when blade `rpm == 0` or blade `speed == 0`.
- `rtk_signal` maps `4` → Strong, `5` → Medium, everything else → Weak.
- `planning_status` and `recharging_status` map device status codes to readable enums.
- `Positioning Confidence` is a direct 0–1 scalar.
- Proximity sensors treat `9999` as the no-obstacle sentinel.

---

## Sensors

### Core device status

| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_battery` | `BatteryMSG.capacity` | `%` | Battery capacity; `battery_capacity` rescales 95 → 100. |
| `sensor.<sn>_error_code` | `StateMSG.error_code` | — | Raw integer fault code. |
| `sensor.<sn>_heart_beat_state` | `HeartBeatMSG.working_state` | enum | `0` → standby, `1` → working. |
| `sensor.<sn>_network` | `route_priority` | enum | `network_priority` maps `hg0` → Halow, `wlan0` → Wifi, `wwan0` → 4G. |
| `sensor.<sn>_rtk_signal` | `RTKMSG.status` | enum | `rtk_signal` maps signal quality to Strong / Medium / Weak. |
| `sensor.<sn>_auto_plan_status` | `StateMSG.on_going_planning` | enum | `planning_status` maps planner state machine. |
| `sensor.<sn>_auto_plan_pause_status` | `StateMSG.planning_paused` | enum | Pause reason code. |
| `sensor.<sn>_recharging_status` | `StateMSG.on_going_recharging` | enum | `recharging_status` maps dock-return workflow state. |
| `sensor.<sn>_volume` | `StateMSG.volume` | `%` | `volume_scale` converts device `0–1` to `0–100`. |
| `sensor.<sn>_head_type` | `HeadMsg.head_type` | enum | Attachment type code. |
| `sensor.<sn>_head_serial_number` | `HeadSerialMsg.head_sn` | — | Attached head serial number. |

### Position / path

| Entity | Source | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_position_x` | `CombinedOdom.x` | m | Disabled by default; raw odometry X. |
| `sensor.<sn>_position_y` | `CombinedOdom.y` | m | Disabled by default; raw odometry Y. |
| `sensor.<sn>_heading` | `CombinedOdom.phi` | ° | Disabled by default; raw heading. |
| `sensor.<sn>_map_zones` | REST `get_map` | — | State = zone count; attributes include GeoJSON FeatureCollection. |
| `sensor.<sn>_current_plan` | `plan_feedback.areaIds` | — | Current plan name from plan feedback. |
| `sensor.<sn>_clean_area` | `plan_feedback.actualCleanArea` | m² | Current-run cleaned area. |
| `sensor.<sn>_battery_consumption` | `plan_feedback.battery_consumption` | % | Current-run battery consumption. |
| `sensor.<sn>_plan_progress` | computed | % | `actualCleanArea / totalCleanArea × 100`. |
| `sensor.<sn>_remaining_area` | computed | m² | `totalCleanArea - actualCleanArea`. |
| `sensor.<sn>_estimated_time_remaining` | `plan_feedback.leftTime` | s | Duration sensor. |
| `sensor.<sn>_elapsed_time` | `plan_feedback.duration` | s | Duration sensor. |
| `sensor.<sn>_total_plan_area` | `plan_feedback.totalCleanArea` | m² | Current plan total area. |
| `sensor.<sn>_total_plan_time` | `plan_feedback.totalTime` | s | Current plan total time. |
| `sensor.<sn>_plan_path` | `plan_feedback.path` / websocket | — | GeoJSON path trace. |

### Raw telemetry families

| Family | Entities | Notes |
|---|---|---|
| Wheel speed / odometry | `Speed`, `Odometry Left`, `Odometry Forward Left`, `Odometry Reverse Left`, `Odometry Right`, `Odometry Total Left`, `Odometry Total Forward Left`, `Odometry Total Reverse Left`, `Odometry Total Right`, `Positioning Confidence` | `Speed` averages left/right wheel speed; left odometry exposes raw signed direction plus derived forward/reverse/total accumulators. |
| Proximity / chute | `Proximity Left`, `Proximity Center`, `Proximity Right`, `Chute Angle` | Proximity uses `9999` as no-obstacle sentinel. `Chute Angle` is snow-blower head only. |

| Head gyro | `Head Gyro Pitch`, `Head Gyro Roll` | Disabled by default. |
| Body IMU | `Body Gyro Pitch`, `Body Gyro Roll`, `Body Gyro Yaw`, `Body Acceleration X/Y/Z`, `Body Angular Velocity X/Y/Z` | Disabled by default. |
| Running status misc | `Impact Sensor`, `Push Pod Status`, `Push Rod Place` | Disabled by default. |
| Electric / track | `Left Wheel Current`, `Right Wheel Current`, `Left Wheel Motor Power`, `Right Wheel Motor Power`, `Brushless Motor Current`, `Push Pod Current`, `Chute Steering Current`, `Chute Current`, `MOS Temperature`, `Motor NTC Temperature` | Track current/power zero when idle (`Speed == 0` and `StateMSG.activity == "Not Started"`). Track power is computed from battery voltage × current. |
| Mower blades | `Middle Blade Current`, `Middle Blade RPM`, `Middle Blade Speed`, `Middle Blade Temperature`, `Middle Blade Temp Status`, `Middle Blade Error`, `Middle Blade Overcurrent`, `Left Blade Current`, `Left Blade Power`, `Left Blade RPM`, `Left Blade Speed`, `Left Blade Temperature`, `Left Blade Temp Status`, `Left Blade Error`, `Left Blade Overcurrent`, `Right Blade Current`, `Right Blade Power`, `Right Blade RPM`, `Right Blade Speed`, `Right Blade Temperature`, `Right Blade Temp Status`, `Right Blade Error`, `Right Blade Overcurrent`, `Lift Motor Current`, `Lift Motor Place`, `Raise Sensor` | Blade current is fixed-point ÷100 A. Blade power is computed from battery voltage × scaled current. Left/right blade current and power zero when `rpm == 0` or `speed == 0`. Middle blade sensors are documented, but the middle-blade firmware mapping still needs validation against live payloads. |
| Wireless recharge | `Wireless Charge Voltage`, `Wireless Charge Current`, `Wireless Charge Temperature`, `Wireless Charge State` | Voltage/current are normalized from fixed-point raw values when `abs(value) > 1000`. |
| RTK / location | `RTK Heading`, `RTK Latitude`, `RTK Longitude`, `RTK Altitude` | `RTK Latitude` uses firmware key `lan` (typo preserved in code). |
| System info | `CPU Temperature`, `CPU Usage`, `CPU Frequency`, `Memory Free`, `Memory Total`, `Memory Available`, `Disk Available`, `Disk Used` | Disabled by default except CPU temperature and CPU usage. |
| Hardware / version strings | `Body Hardware Version`, `Head Hardware Version`, `Radar Hardware Version`, `Chassis Firmware Version`, `Firmware Package Version`, `BLE Version`, `Base Station Name` | String-valued sensors. |
| Flat numeric | `Base Station Status`, `Position Deviation`, `RTCM Correction Age` | Top-level numeric sensors. |

### Detailed notes

#### Battery
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_battery` |
| MQTT path | `BatteryMSG.capacity` |
| Unit | `%` |
| Device class | `battery` |
| State class | `measurement` |
| Notes | Integer 0–100. Updates roughly every 35 min while charging, every 1–2 min while running. |

#### Error Code
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_error_code` |
| MQTT path | `StateMSG.error_code` |
| Unit | — |
| Notes | Raw integer error code from device. `0` = no error. Non-zero values are device-specific fault codes. |

#### Heart Beat State
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_heart_beat_state` |
| MQTT path | `HeartBeatMSG.working_state` |
| Device class | `enum` |
| Value map | `0` → `standby`, `1` → `working` |
| Notes | Updated on every heartbeat (~5 s). Reflects device operating mode. |

#### Network
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_network` |
| MQTT path | `route_priority` |
| Device class | `enum` |
| Extractor | `network_priority` (custom) |
| Value map | `hg0` → `Halow`, `wlan0` → `Wifi`, `wwan0` → `4G` |
| Notes | Active network interface. `Halow` = long-range Wi-Fi. |

#### RTK Signal
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_rtk_signal` |
| MQTT path | `RTKMSG.status` |
| Device class | `enum` |
| Extractor | `rtk_signal` (custom) |
| Values | `Strong`, `Medium`, `Weak` |
| Notes | GPS/RTK fix quality. Weak signal may cause navigation errors. |

#### Auto Plan Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_auto_plan_status` |
| MQTT path | `StateMSG.on_going_planning` |
| Device class | `enum` |
| Extractor | `planning_status` (custom) |
| Key values | `Not Started`, `Cleaning`, `Calculating Route`, `Heading to Area`, `Completed`, `Waypoint Navigation`, `Waypoint Complete`, `Error: *` |
| Notes | Integer status code mapped to human-readable string. Error states include WP-prefixed fault codes. |

#### Auto Plan Pause Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_auto_plan_pause_status` |
| MQTT path | `StateMSG.planning_paused` |
| Device class | `enum` |
| Value map | `0` = Not Paused, `1` = Manual Pause, `2` = Low Battery Recharging, `3` = Power Restart, `4` = E-Stop, `5` = Bumper, `6` = Stuck, `7` = Error |

#### Recharging Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_recharging_status` |
| MQTT path | `StateMSG.on_going_recharging` |
| Device class | `enum` |
| Extractor | `recharging_status` (custom) |
| Key values | `Not Started`, `Returning on Path`, `Returning in Area`, `Repositioning`, `Charging`, `Verifying`, `Error: *` |
| Notes | Tracks the dock-return workflow state, not battery charge level. `Charging` = physically docked and in charging sequence. |

#### Volume
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_volume` |
| MQTT path | `StateMSG.volume` |
| Unit | `%` |
| Extractor | `volume_scale` — device reports 0–1 float, scaled ×100 for display |

#### Head Type
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_head_type` |
| MQTT path | `HeadMsg.head_type` |
| Device class | `enum` |
| Value map | `0` = None, `1` = Snow Blower, `2` = Blower, `3` = Mower, `4` = Smart Cover, `5` = Mower Pro |

#### Head Serial Number
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_head_serial_number` |
| MQTT path | `HeadSerialMsg.head_sn` |
| Notes | Serial number of the attached head attachment. |

#### Position X / Y *(disabled by default)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_position_x`, `sensor.<sn>_position_y` |
| MQTT path | `CombinedOdom.x`, `CombinedOdom.y` |
| Unit | `m` |
| Notes | Raw odometry position in meters relative to GPS reference origin. Enable to expose raw coordinates; the Device Tracker converts these to GPS. |

#### Heading *(disabled by default)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_heading` |
| MQTT path | `CombinedOdom.phi` |
| Unit | `°` |
| Notes | Robot heading in degrees. |

#### Map Zones
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_map_zones` |
| Source | `get_map` REST response |
| Notes | State = total zone count. `extra_state_attributes.geojson` = GeoJSON FeatureCollection of all no-go and work zones for use with HA map card. Attributes exceed HA's recorder-friendly size budget, so they are not intended for history. |

#### Current Plan
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_current_plan` |
| Source | `plan_feedback.areaIds` matched against plan list |
| Notes | Name of the plan currently running. `None` when no plan is active. Updated via `plan_feedback` MQTT push. |

#### Completed Plan Area
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_clean_area` |
| Source | `plan_feedback.actualCleanArea` |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Area covered in the current plan run. Resets to 0 at plan start. |

#### Plan Battery Consumption
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_battery_consumption` |
| Source | `plan_feedback.battery_consumption` |
| Unit | `%` |
| State class | `measurement` |
| Notes | Battery percentage consumed during the current plan run. |

#### Plan Progress
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_plan_progress` |
| Source | `actualCleanArea / totalCleanArea × 100` (computed) |
| Unit | `%` |
| State class | `measurement` |
| Notes | Plan completion 0–100%. `None` when no plan is active. |

#### Remaining Plan Area
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_remaining_area` |
| Source | `totalCleanArea - actualCleanArea` (computed) |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Area remaining in the current plan. `None` when no plan is active. |

#### Estimated Time Remaining
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_estimated_time_remaining` |
| Source | `plan_feedback.leftTime` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Device-estimated seconds until plan completion. |

#### Plan Elapsed Time
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_elapsed_time` |
| Source | `plan_feedback.duration` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Seconds elapsed since the current plan started. |

#### Total Plan Area
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_total_plan_area` |
| Source | `plan_feedback.totalCleanArea` |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Total mapped area of the current plan. Stable during a run. |

#### Total Plan Time
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_total_plan_time` |
| Source | `plan_feedback.totalTime` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Device-estimated total duration for the full plan. |

#### Speed
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_speed` |
| Source | `WheelSpeedMSG.left` / `WheelSpeedMSG.right` |
| Unit | `m/s` |
| Notes | Average forward speed derived from wheel encoders. |

#### Odometry Left / Right
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_odometry_left`, `sensor.<sn>_odometry_right` |
| Source | `WheelSpeedMSG.dist_left`, `WheelSpeedMSG.dist_right` |
| Unit | `m` |
| Notes | Raw wheel odometry since power-on. |

#### Odometry Total Left / Right
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_odometry_total_left`, `sensor.<sn>_odometry_total_right` |
| Source | Raw odometry deltas accumulated across power cycles |
| Unit | `m` |
| Notes | Persisted totals. |

#### Positioning Confidence
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_odom_confidence` |
| Source | `combined_odom_confidence` |
| Unit | 0–1 |`
| Notes | Fused odometry / positioning confidence. |

#### Chute Angle
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_chute_angle` |
| Source | `RunningStatusMSG.chute_angle` |
| Unit | `°` |
| Notes | Snow blower head only. |

#### Proximity sensors
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_proximity_left` | `ultrasonic_msg.lf_dis` | mm | `9999` sentinel means no obstacle. |
| `sensor.<sn>_proximity_center` | `ultrasonic_msg.mt_dis` | mm | `9999` sentinel means no obstacle. |
| `sensor.<sn>_proximity_right` | `ultrasonic_msg.rf_dis` | mm | `9999` sentinel means no obstacle. |

#### Head gyro
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_gyro_pitch` | `RunningStatusMSG.head_gyro_pitch` | ° | Disabled by default. |
| `sensor.<sn>_gyro_roll` | `RunningStatusMSG.head_gyro_roll` | ° | Disabled by default. |

#### Body IMU
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_body_gyro_pitch` | `RunningStatusMSG.gyro_pitch` | ° | Disabled by default. |
| `sensor.<sn>_body_gyro_roll` | `RunningStatusMSG.gyro_roll` | ° | Disabled by default. |
| `sensor.<sn>_body_gyro_yaw` | `RunningStatusMSG.gyro_yaw` | ° | Disabled by default. |
| `sensor.<sn>_body_acc_x` | `RunningStatusMSG.gyro_acc_x` | m/s² | Disabled by default. |
| `sensor.<sn>_body_acc_y` | `RunningStatusMSG.gyro_acc_y` | m/s² | Disabled by default. |
| `sensor.<sn>_body_acc_z` | `RunningStatusMSG.gyro_acc_z` | m/s² | Disabled by default. |
| `sensor.<sn>_body_ang_vel_x` | `RunningStatusMSG.gyro_ang_vel_x` | rad/s | Disabled by default. |
| `sensor.<sn>_body_ang_vel_y` | `RunningStatusMSG.gyro_ang_vel_y` | rad/s | Disabled by default. |
| `sensor.<sn>_body_ang_vel_z` | `RunningStatusMSG.gyro_ang_vel_z` | rad/s | Disabled by default. |

#### Running status misc
| Entity | MQTT path | Notes |
|---|---|---|
| `sensor.<sn>_impact_sensor` | `RunningStatusMSG.impact_sensor` | Disabled by default. |
| `sensor.<sn>_push_pod_status` | `RunningStatusMSG.push_pod_status` | Disabled by default. |
| `sensor.<sn>_push_rod_place` | `RunningStatusMSG.push_rod_place` | Disabled by default. |

#### Electric / track
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_left_wheel_current` | `EletricMSG.lwheel_current` | A | Zeroed when idle. |
| `sensor.<sn>_right_wheel_current` | `EletricMSG.rwheel_current` | A | Zeroed when idle. |
| `sensor.<sn>_left_wheel_motor_power` | computed from `EletricMSG.lwheel_current × BatteryMSG.voltage` | W | Zeroed when idle. |
| `sensor.<sn>_right_wheel_motor_power` | computed from `EletricMSG.rwheel_current × BatteryMSG.voltage` | W | Zeroed when idle. |
| `sensor.<sn>_brushless_motor_current` | `EletricMSG.brushless_motor_current` | A | Pass-through. |
| `sensor.<sn>_push_pod_current` | `EletricMSG.push_pod_current` | A | Pass-through. |
| `sensor.<sn>_chute_steering_current` | `EletricMSG.chute_streeing_engine_current` | A | Firmware typo preserved in raw key. |
| `sensor.<sn>_chute_current` | `EletricMSG.current_chute` | A | Snow blower head only. |
| `sensor.<sn>_mos_temp` | `EletricMSG.mos_temp` | °C | Pass-through. |
| `sensor.<sn>_motor_ntc_temp` | `EletricMSG.ntc_temperature` | °C | Pass-through. |

#### Mower blades
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_middle_blade_current` | `mower_head_info02.middle_blade_motor_current` | A | Documented; middle-blade mapping still needs live payload validation. |
| `sensor.<sn>_middle_blade_rpm` | `mower_head_info02.middle_blade_motor_rpm` | rpm | Documented; live validation pending. |
| `sensor.<sn>_middle_blade_speed` | `mower_head_info02.middle_blade_motor_speed` | % | Documented; live validation pending. |
| `sensor.<sn>_middle_blade_temperature` | `mower_head_info02.middle_blade_motor_temp` | °C | Documented; live validation pending. |
| `sensor.<sn>_middle_blade_temp_status` | `mower_head_info02.middle_blade_motor_temp_status` | enum | Documented; live validation pending. |
| `sensor.<sn>_middle_blade_error` | `mower_head_info02.middle_blade_motor_err` | enum | Documented; live validation pending. |
| `sensor.<sn>_middle_blade_overcurrent` | `mower_head_info02.middle_blade_motor_over_current_info` | enum | Documented; live validation pending. |
| `sensor.<sn>_left_blade_current` | `mower_head_info03.left_blade_motor_current` | A | Fixed-point ÷100. Zero when rpm or speed is 0. |
| `sensor.<sn>_left_blade_power` | computed from `mower_head_info03.left_blade_motor_current × BatteryMSG.voltage` | W | Fixed-point current ÷100; zero when rpm or speed is 0. |
| `sensor.<sn>_left_blade_rpm` | `mower_head_info03.left_blade_motor_rpm` | rpm | Returns absolute value; direction lives in attributes. |
| `sensor.<sn>_left_blade_speed` | `mower_head_info03.left_blade_motor_speed` | % | Pass-through. |
| `sensor.<sn>_left_blade_temperature` | `mower_head_info03.left_blade_motor_temp` | °C | Pass-through. |
| `sensor.<sn>_left_blade_temp_status` | `mower_head_info03.left_blade_motor_temp_status` | enum | Pass-through. |
| `sensor.<sn>_left_blade_error` | `mower_head_info03.left_blade_motor_err` | enum | Pass-through. |
| `sensor.<sn>_left_blade_overcurrent` | `mower_head_info03.left_blade_motor_over_current_info` | enum | Pass-through. |
| `sensor.<sn>_right_blade_current` | `mower_head_info04.right_blade_motor_current` | A | Fixed-point ÷100. Zero when rpm or speed is 0. |
| `sensor.<sn>_right_blade_power` | computed from `mower_head_info04.right_blade_motor_current × BatteryMSG.voltage` | W | Fixed-point current ÷100; zero when rpm or speed is 0. |
| `sensor.<sn>_right_blade_rpm` | `mower_head_info04.right_blade_motor_rpm` | rpm | Pass-through. |
| `sensor.<sn>_right_blade_speed` | `mower_head_info04.right_blade_motor_speed` | % | Pass-through. |
| `sensor.<sn>_right_blade_temperature` | `mower_head_info04.right_blade_motor_temp` | °C | Pass-through. |
| `sensor.<sn>_right_blade_temp_status` | `mower_head_info04.right_blade_motor_temp_status` | enum | Pass-through. |
| `sensor.<sn>_right_blade_error` | `mower_head_info04.right_blade_motor_err` | enum | Pass-through. |
| `sensor.<sn>_right_blade_overcurrent` | `mower_head_info04.right_blade_motor_over_current_info` | enum | Pass-through. |
| `sensor.<sn>_lift_motor_current` | `mower_head_info01.lift_motor_current` | A | Pass-through. |
| `sensor.<sn>_lift_motor_place` | `mower_head_info01.lift_motor_place` | — | Pass-through. |
| `sensor.<sn>_raise_sensor` | `mower_head_info01.raise_sensor` | — | Pass-through. |

#### Wireless recharge
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_wireless_charge_voltage` | `wireless_recharge.output_voltage` | V | Fixed-point values divide by 1000 when raw magnitude > 1000. |
| `sensor.<sn>_wireless_charge_current` | `wireless_recharge.output_current` | A | Fixed-point values divide by 1000 when raw magnitude > 1000. |
| `sensor.<sn>_wireless_charge_temperature` | `wireless_recharge.temperature` | °C | Pass-through. |
| `sensor.<sn>_wireless_charge_state` | `wireless_recharge.state` | — | Pass-through state code. |

#### RTK / location
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_rtk_heading` | `RTKMSG.heading` | ° | Pass-through. |
| `sensor.<sn>_rtk_latitude` | `RTKMSG.lan` | ° | Firmware key name is `lan` (typo preserved). |
| `sensor.<sn>_rtk_longitude` | `RTKMSG.lon` | ° | Pass-through. |
| `sensor.<sn>_rtk_altitude` | `RTKMSG.hgt` | m | Pass-through. |

#### System info
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_cpu_temperature` | `system_info.cpu.Temperature` | °C | Enabled by default. |
| `sensor.<sn>_cpu_usage` | `system_info.cpu.Usage` | % | Enabled by default. |
| `sensor.<sn>_cpu_frequency` | `system_info.cpu.Frequency` | MHz | Disabled by default. |
| `sensor.<sn>_mem_free` | `system_info.mem.MemFree` | kB | Disabled by default. |
| `sensor.<sn>_mem_total` | `system_info.mem.MemTotal` | kB | Disabled by default. |
| `sensor.<sn>_mem_available` | `system_info.mem.MemAvailable` | kB | Disabled by default. |
| `sensor.<sn>_disk_available` | `system_info.userdata.disk.availableSize` | B | Disabled by default. |
| `sensor.<sn>_disk_used` | `system_info.userdata.disk.usedSize` | B | Disabled by default. |

#### Hardware / version strings
| Entity | MQTT path | Notes |
|---|---|---|
| `sensor.<sn>_body_hardware_version` | `hardware_version.body_version` | String sensor. |
| `sensor.<sn>_head_hardware_version` | `hardware_version.head_version` | String sensor. |
| `sensor.<sn>_radar_hardware_version` | `hardware_version.radar_version` | String sensor. |
| `sensor.<sn>_chassis_version` | `chassis_version_msg.firmware_version` | String sensor. |
| `sensor.<sn>_firmware_package_version` | `version` | String sensor. |
| `sensor.<sn>_ble_version` | `ble_version` | String sensor. |
| `sensor.<sn>_base_name` | `base_name` | String sensor. |

#### Flat numeric
| Entity | MQTT path | Unit | Notes |
|---|---|---|---|
| `sensor.<sn>_base_status` | `base_status` | — | Flat numeric code. |
| `sensor.<sn>_position_deviation` | `pos_devia_dis` | m | Flat numeric sensor. |
| `sensor.<sn>_rtcm_age` | `rtcm_age` | s | Flat numeric sensor. |

---

## Binary Sensors

### Online
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_online` |
| Source | Heartbeat timer — `on` while heartbeats arrive within 15 s |
| Device class | `connectivity` |
| Notes | Driven by the heartbeat check timer (runs every 5 s). Not a field from MQTT payload. |

### Active Charge
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_charging` |
| MQTT path | `BatteryMSG.status` |
| Device class | `battery_charging` |
| Threshold | `on` when `BatteryMSG.status > 1` |
| Attribute | `battery_status_raw` — exposes the raw integer for threshold debugging |

### Sound Enabled
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_sound_enabled` |
| MQTT path | `StateMSG.enable_sound` |
| Notes | `on` when device sounds are enabled. |

### Headlight
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_headlight` |
| MQTT path | `LedInfoMSG.led_head` |
| Threshold | `on` when `led_head > 0` |

---

## Controls

### Working State
| Entity | `select.<sn>_working_state` |
| MQTT path (read) | `HeartBeatMSG.working_state` |
| Command topic | `set_working_state` |
| Options | `standby`, `working` |

### Plan Select
| Entity | `select.<sn>_plan_select` |
| Source | Plan list from `read_all_plan` REST call |
| Notes | Reflects the current running plan when one is active; otherwise the user's selection. |

### Sound Switch
| Entity | `switch.<sn>_sound_switch` |
| MQTT path (read) | `StateMSG.enable_sound` |
| Command topic | `set_sound_param` |

### Headlight
| Entity | `switch.<sn>_headlight` |
| MQTT path (read) | `LedInfoMSG.led_head` |
| Command topic | `light_ctrl` |

### Volume
| Entity | `number.<sn>_volume` |
| MQTT path (read) | `StateMSG.volume` |
| Range | 0–100 % |
| Command topic | `set_sound_param` |
| Notes | Device reports 0–1 float; UI shows 0–100. Conversion is applied on both read and write. |

### Plan Start Percent
| Entity | `number.<sn>_plan_start_percent` |
| Range | 0–99 % |
| Notes | Local state only. Used as the battery threshold below which the plan is paused to recharge. |

### Service
| Entity | `yarbo.set_nogozone_enabled` |
| Notes | Toggles no-go-zone enablement by firmware-aware MQTT encoding. |

---

## Device Tracker

| Property | Value |
|---|---|
| Entity | `device_tracker.<sn>_location` |
| Source | `CombinedOdom.x` / `CombinedOdom.y` converted to lat/lon |
| Conversion | `convert_local_to_gps(ref_lat, ref_lon, x_m, y_m)` using GPS reference origin |
| Notes | Requires GPS reference to have been fetched. Position is in meters relative to the reference origin and converted to absolute GPS for the HA map card. |

---

## Notes

- Large GeoJSON attributes belong in dedicated sensors or the websocket API, not in recorder-heavy state attributes.
- Sensors documented as disabled by default are still part of the integration’s metric inventory; they are just hidden unless explicitly enabled.
