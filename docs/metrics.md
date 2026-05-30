# Yarbo BG — Entity & Metric Reference

All data arrives via MQTT push from the device. There is no polling —
entities update only when the device sends a new message. MQTT field
paths use dot notation into the raw device payload.

---

## Sensors

### Battery
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_battery` |
| MQTT path | `BatteryMSG.capacity` |
| Unit | `%` |
| Device class | `battery` |
| State class | `measurement` |
| Notes | Integer 0–100. Updates roughly every 35 min while charging, every 1–2 min while running. |

### Error Code
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_error_code` |
| MQTT path | `StateMSG.error_code` |
| Unit | — |
| Notes | Raw integer error code from device. `0` = no error. Non-zero values are device-specific fault codes. |

### Heart Beat State
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_heart_beat_state` |
| MQTT path | `HeartBeatMSG.working_state` |
| Device class | `enum` |
| Value map | `0` → `standby`, `1` → `working` |
| Notes | Updated on every heartbeat (~5 s). Reflects device operating mode. |

### Network
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_network` |
| MQTT path | `route_priority` |
| Device class | `enum` |
| Extractor | `network_priority` (custom) |
| Value map | `hg0` → `Halow`, `wlan0` → `Wifi`, `wwan0` → `4G` |
| Notes | Active network interface. `Halow` = 900 MHz long-range Wi-Fi. |

### RTK Signal
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_rtk_signal` |
| MQTT path | `RTKMSG.status` |
| Device class | `enum` |
| Extractor | `rtk_signal` (custom) |
| Values | `Strong`, `Medium`, `Weak` |
| Notes | GPS/RTK fix quality. Weak signal may cause navigation errors. |

### Auto Plan Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_auto_plan_status` |
| MQTT path | `StateMSG.on_going_planning` |
| Device class | `enum` |
| Extractor | `planning_status` (custom) |
| Key values | `Not Started`, `Cleaning`, `Calculating Route`, `Heading to Area`, `Completed`, `Waypoint Navigation`, `Waypoint Complete`, `Error: *` |
| Notes | Integer status code mapped to human-readable string. Error states include WP-prefixed fault codes. |

### Auto Plan Pause Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_auto_plan_pause_status` |
| MQTT path | `StateMSG.planning_paused` |
| Device class | `enum` |
| Value map | `0` = Not Paused, `1` = Manual Pause, `2` = Low Battery Recharging, `3` = Power Restart, `4` = E-Stop, `5` = Bumper, `6` = Stuck, `7` = Error |

### Recharging Status
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_recharging_status` |
| MQTT path | `StateMSG.on_going_recharging` |
| Device class | `enum` |
| Extractor | `recharging_status` (custom) |
| Key values | `Not Started`, `Returning on Path`, `Returning in Area`, `Repositioning`, `Charging`, `Verifying`, `Error: *` |
| Notes | Tracks the dock-return workflow state, not battery charge level. `Charging` = physically docked and in charging sequence. |

### Volume
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_volume` |
| MQTT path | `StateMSG.volume` |
| Unit | `%` |
| Extractor | `volume_scale` — device reports 0–1 float, scaled ×100 for display |

### Head Type
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_head_type` |
| MQTT path | `HeadMsg.head_type` |
| Device class | `enum` |
| Value map | `0` = None, `1` = Snow Blower, `2` = Blower, `3` = Mower, `4` = Smart Cover, `5` = Mower Pro |

### Head Serial Number
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_head_serial_number` |
| MQTT path | `HeadSerialMsg.head_sn` |
| Notes | Serial number of the attached head attachment. |

### Position X / Y *(disabled by default)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_position_x`, `sensor.<sn>_position_y` |
| MQTT path | `CombinedOdom.x`, `CombinedOdom.y` |
| Unit | `m` |
| Notes | Raw odometry position in meters relative to GPS reference origin. Enable to expose raw coordinates; the Device Tracker converts these to GPS. |

### Heading *(disabled by default)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_heading` |
| MQTT path | `CombinedOdom.phi` |
| Unit | `°` |
| Notes | Robot heading in degrees. |

### Map Zones
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_map_zones` |
| Source | `get_map` REST response |
| Notes | State = total zone count. `extra_state_attributes.geojson` = GeoJSON FeatureCollection of all no-go and work zones for use with HA map card. **Attributes exceed HA's 16 KB recorder limit — not stored in history.** |

### Current Plan *(new in 0.4.6)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_current_plan` |
| Source | `plan_feedback.areaIds` matched against plan list |
| Notes | Name of the plan currently running (e.g. "South Front"). `None` when no plan is active. Updated via `plan_feedback` MQTT push. |

### Clean Area *(new in 0.4.6)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_clean_area` |
| Source | `plan_feedback.actualCleanArea` |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Area covered in the current run. Resets to 0 at plan start. |

### Battery Consumption *(new in 0.4.6)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_battery_consumption` |
| Source | `plan_feedback.battery_consumption` |
| Unit | `%` |
| State class | `measurement` |
| Notes | Battery percentage consumed during the current run. |

### Plan Progress *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_plan_progress` |
| Source | `actualCleanArea / totalCleanArea × 100` (computed) |
| Unit | `%` |
| State class | `measurement` |
| Notes | Plan completion 0–100%. `None` when no plan is active. |

### Remaining Area *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_remaining_area` |
| Source | `totalCleanArea - actualCleanArea` (computed) |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Area left to clean. `None` when no plan is active. |

### Estimated Time Remaining *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_estimated_time_remaining` |
| Source | `plan_feedback.leftTime` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Device-estimated seconds until plan completion. |

### Elapsed Time *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_elapsed_time` |
| Source | `plan_feedback.duration` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Seconds since the current plan started. |

### Total Plan Area *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_total_plan_area` |
| Source | `plan_feedback.totalCleanArea` |
| Unit | `m²` |
| State class | `measurement` |
| Notes | Total mapped area of the current plan. Stable during a run. |

### Total Plan Time *(new in 0.4.7)*
| Property | Value |
|---|---|
| Entity ID pattern | `sensor.<sn>_total_plan_time` |
| Source | `plan_feedback.totalTime` |
| Unit | `s` |
| Device class | `duration` |
| State class | `measurement` |
| Notes | Device-estimated total duration for the full plan. |

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
| Notes | Distinct from "Recharging Status" which tracks the dock-return workflow. This sensor indicates whether the battery is *actively* receiving current. Threshold under observation (may need to be `>= 1`). |

### Sound Enabled
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_sound_enabled` |
| MQTT path | `StateMSG.enable_sound` |
| Notes | `on` when device sounds are enabled. Reflects current state from MQTT; controlled via Sound Switch entity. |

### Headlight
| Property | Value |
|---|---|
| Entity ID pattern | `binary_sensor.<sn>_headlight` |
| MQTT path | `LedInfoMSG.led_head` |
| Threshold | `on` when `led_head > 0` (255 = full brightness) |
| Notes | Read-only status mirror. Controlled via the Headlight switch entity. |

---

## Controls

### Working State
| Property | Value |
|---|---|
| Entity | `select.<sn>_working_state` |
| MQTT path (read) | `HeartBeatMSG.working_state` |
| Command topic | `set_working_state` |
| Options | `standby`, `working` |
| Notes | Setting `working` sends a wake-up command. Setting `standby` suppresses the auto wake-up renewal. Extra payload: `{"source": "smart_home"}`. |

### Plan Select
| Property | Value |
|---|---|
| Entity | `select.<sn>_plan_select` |
| Source | Plan list from `read_all_plan` REST call |
| Notes | Selects which plan to run. State reflects the currently active plan (from `plan_feedback`) when one is running; falls back to the user's last manual selection. Pressing Start Plan executes the selected plan. |

### Sound Switch
| Property | Value |
|---|---|
| Entity | `switch.<sn>_sound_switch` |
| MQTT path (read) | `StateMSG.enable_sound` |
| Command topic | `set_sound_param` |
| Builder | `sound_switch` |

### Headlight
| Property | Value |
|---|---|
| Entity | `switch.<sn>_headlight` |
| MQTT path (read) | `LedInfoMSG.led_head` |
| Command topic | `light_ctrl` |
| Builder | `light_switch` |

### Volume
| Property | Value |
|---|---|
| Entity | `number.<sn>_volume` |
| MQTT path (read) | `StateMSG.volume` |
| Range | 0–100 % |
| Command topic | `set_sound_param` |
| Builder | `sound_volume` |
| Notes | Device reports 0–1 float; UI shows 0–100. Conversion is applied on both read and write. |

### Plan Start Percent
| Property | Value |
|---|---|
| Entity | `number.<sn>_plan_start_percent` |
| Range | 0–99 % |
| Notes | Local state only (not reflected in device data). Passed to Start Plan as the battery threshold below which the plan is paused to recharge. |

---

## Buttons

| Button | Action | Safety checks |
|---|---|---|
| Start Plan | Execute selected plan at `plan_start_percent` | Battery ≥ `plan_start_percent`, not recharging, device must be reachable |
| Pause Plan | Pause current plan | — |
| Resume Plan | Resume paused plan | — |
| Stop Plan | Stop and cancel current plan | — |
| Return to Charge | Send device to charging station | Device must not be already recharging |
| Refresh Plans | Re-fetch plan list from device | — |
| Refresh GPS Reference | Re-fetch GPS origin coordinates | — |
| Refresh Map Data | Re-fetch map/zone data | — |
| Refresh Device Data | Re-fetch full DeviceMSG snapshot | — |

---

## Device Tracker

| Property | Value |
|---|---|
| Entity | `device_tracker.<sn>_location` |
| Source | `CombinedOdom.x` / `CombinedOdom.y` converted to lat/lon |
| Conversion | `convert_local_to_gps(ref_lat, ref_lon, x_m, y_m)` using GPS reference origin |
| Notes | Requires GPS reference (`Refresh GPS Reference`) to have been fetched. Position is in meters relative to the reference origin and converted to absolute GPS for the HA map card. |

---

## Service

### `yarbo_bg.set_nogozone_enabled`

Enable or disable an individual no-go zone on the device map.

| Field | Type | Description |
|---|---|---|
| `device_id` | device | HA device ID of the Yarbo unit |
| `zone_id` | string or int | ID of the zone (from map data) |
| `enabled` | boolean | `true` to activate the zone, `false` to deactivate |

**Restrictions:** Cannot be called while a plan is actively running (`on_going_planning > 0` and `≠ 5`). Publishes directly to `snowbot/<sn>/app/save_nogozone` with the full zone payload.
