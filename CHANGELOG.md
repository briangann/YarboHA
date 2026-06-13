# Changelog

What's new in each release of Yarbo.

---

## [0.5.0] - 2026-06-04

Domain reverted from `yarbo_bg` back to `yarbo` to align with upstream. Integration name is now **Yarbo**.

### ⚠️ Breaking Change — Entity ID Migration Required
Entity IDs change from `yarbo_bg.*` to `yarbo.*`. After updating:
1. Remove the Yarbo integration (**Settings → Devices & Services → Yarbo BG → Delete**).
2. Restart Home Assistant.
3. Re-add the integration (**Add Integration → Yarbo**) and reconfigure credentials + devices.
4. Update any automations, scripts, or dashboards that reference `yarbo_bg.*` entity IDs.

### Changed
- Integration domain: `yarbo_bg` → `yarbo`
- Integration display name: **Yarbo BG** → **Yarbo**
- Service: `yarbo_bg.set_nogozone_enabled` → `yarbo.set_nogozone_enabled`
- Package path: `custom_components/yarbo_bg/` → `custom_components/yarbo/`

This changelog follows the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format and adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.1] - 2026-06-13

Upstream sync from YarboInc monorepo (commits b009815a + 37edd28b).

### New
- **WebSocket map API** — GeoJSON zone map served on demand via `yarbo/map_zones` WebSocket command instead of entity attributes, avoiding Home Assistant's 16 KB attribute limit
- **Entity filters** — `entity_filters.py` provides `control_matches_device()` to suppress head-specific controls when the wrong attachment is fitted

### Changed
- **Config-driven sensor and binary sensor** — all ~20 individual sensor classes replaced by `YarboConfigSensor` / `YarboConfigBinarySensor` driven by SDK field definitions; adds `battery_capacity` rescaling (firmware caps at 95%, rescaled to 100%), `charging_power` computed from voltage × current, and new `custom_extractor` variants
- **Coordinator rewrite** — storage persistence via `homeassistant.helpers.storage`, keep-awake mode policy (`CONF_KEEP_AWAKE_MODE`: always / docked / off), typed SDK dispatch via `BoundDevice` API with raw MQTT fallback
- **Button, number, select, switch** — route commands through typed SDK `bound_device()` methods where available; fall back to raw MQTT
- **SDK bumped** to `yarbo-data-sdk>=0.2.1` (adds `BoundDevice`, `_ensure_mqtt_for`, dual-broker migration; removes `mqtt_subscribe`/`mqtt_unsubscribe`)
- `manifest.json` adds `websocket_api` HA dependency

### Removed (upstream changes — verify before merge)
- **Plan-completion auto-refresh** — coordinator no longer detects `on_going_planning == 5` to auto-call `_async_fetch_plans`. Plan list will not refresh after a run completes without a manual trigger or HA restart.
- **`yarbo.set_nogozone_enabled` service** — removed without deprecation stub. Automations using this service will fail silently on upgrade. (See decisions needed below.)
- **`YarboOnlineBinarySensor.extra_state_attributes`** — 15 raw telemetry attributes removed (`wheel_speed_left/right_mps`, `speed_mps`, `dist_left/right_m`, `odom_confidence`, `impact_sensor`, `rain_sensor_data`, `head_gyro_pitch/roll`, `chute_angle`, `lf_dis`, `mt_dis`, `rf_dis`, `abnormal_msg`). None are covered by config-driven sensor entities — SDK field definitions do not include these fields. Dashboard cards and automations reading these attributes will silently return `None`.

### Fixed (our additions on top of upstream)
- All `_client` Optional None guards in button, number, select, switch — upstream code accessed `_client` without checking for `None` in fallback branches (silent runtime failure)
- `number.py` — `BoundCoreModule.publish_command(topic, payload)` and `CoreModule.publish_command(sn, topic, payload, type_id)` have different arg counts; upstream ternary was passing wrong args to the bound path
- `device_tracker.py` — `SourceType` imported from correct `.const` submodule
- `config_flow.py` — `str | None` title coerced to `str`; `context["entry_id"]` safe-accessed via `.get()`

---

## [0.5.2] - 2026-06-13

### Documentation
- **AGENTS.md** — updated to reflect current architecture (domain `yarbo`, config-driven entities, SDK 0.2.1, heartbeat timeout 90s, test coverage notes)

### Pre-merge review findings for `feat/upstream-sync-0.3.3`

The following issues were identified during code review and must be resolved or explicitly accepted before merging.

#### ✅ Fixed this session

- **`device_tracker.py` — recorder GPS spam** ✅ Fixed in 971c03a. Reimplemented position
  dedup cache `_last_position`; `async_write_ha_state()` now skipped when lat/lon/available
  unchanged.

- **`map_sensor.py` — broken dedup** ✅ Fixed in 971c03a. `repr()` replaced with
  `json.dumps(sort_keys=True)` for deterministic change detection.
  Note: `geojson` attribute removal is an upstream architectural decision (moved to
  `yarbo/map_zones` WebSocket API). Documented in v0.5.1 Removed section; migration note
  needed in release announcement.

#### 🔴 Regressions (must fix)

- **`binary_sensor.py` — 15 raw telemetry attributes silently gone** ✅ Fixed. Restored
  `extra_state_attributes` on `YarboOnlineBinarySensor` with all 15 fields. Will remain
  until upstream SDK field definitions cover these paths, at which point they can migrate
  to dedicated sensor entities.

#### 🟡 Decisions needed before merge

- **`button.py` — wireless-charging check reversed** Check 4 in `YarboStartPlanButton`
  now blocks plan start when `BatteryMSG.status > 1`. Previous version explicitly
  documented: *"Wireless charging is NOT a blocker — the robot undocks itself."* Upstream
  reversed this without explanation. Needs device-confirmed answer: can the robot
  autonomously undock from wireless charging when a plan is issued?

- **`select.py` — plan select lost running-plan reflection** ✅ Fixed. `current_option`
  now resolves plan name from `coordinator.get_selected_plan()` (tracks selections and
  button starts). Limitation vs old behavior: only reflects plans started through HA;
  plans started from the mobile app won't be reflected (old `plan_feedback` MQTT mechanism
  removed upstream).

- **`__init__.py` — `yarbo.set_nogozone_enabled` service removed** ✅ Restored. Service
  re-registered in `__init__.py`; `async_set_nogozone_enabled()` re-added to coordinator
  using `yarbo_robot_sdk.codec` for firmware-aware encoding and `_ensure_mqtt_for(sn)`
  for dual-broker MQTT publish. Raw map data (`_map_raw`) preserved alongside GeoJSON in
  coordinator so zone mutations have the original payload to modify.

#### 🟢 Documented / low risk

- **`coordinator.py` — plan-completion auto-refresh removed** Documented in v0.5.1
  Removed section. Plan list won't refresh after a run without a manual trigger.

---


## [0.4.11] - 2026-05-30

No more "Unknown" after restarting HA, and status labels that reflect what the robot is actually doing.

### Fixed
- **Unknown entities after restart** — the integration now remembers its last known state (plan list, device data, GPS reference, map data) and restores it immediately on the next startup. Entities that previously showed Unknown until the device responded to requests will now show their last values right away.
- **Auto Plan Status showed "Cleaning" regardless of head type** — now shows the correct verb: *Mowing* (mower / mower pro), *Blowing Snow* (snow blower), *Blowing* (blower), *Working* (smart cover or no head)

---

## [0.4.10] - 2026-05-30

Sensor names cleaned up — the Yarbo does mowing and snowblowing, not "cleaning".

### Changed
- Four sensors renamed to better reflect what the device actually does. Entity IDs are unchanged so existing automations and dashboards are not affected.
  - *Clean Area* → **Completed Plan Area**
  - *Battery Consumption* → **Plan Battery Consumption**
  - *Remaining Area* → **Remaining Plan Area**
  - *Elapsed Time* → **Plan Elapsed Time**

---

## [0.4.9] - 2026-05-30

Bug fixes identified during internal code review.

### Fixed
- **Odometry sensors** were using the wrong recorder category, which could corrupt long-term statistics in Home Assistant. Fixed.
- **Fault sensors** (motor, wheel, radar) could misread non-numeric values from the device as a fault. Fixed with a proper type check.
- **Current Plan** sensor now correctly updates after the device reconnects to the network — previously it could miss the first plan completion after a reconnect.
- Minor reliability improvement: plan list is only fetched once on plan completion, even if multiple status updates arrive simultaneously.

---

## [0.4.8] - 2026-05-30

Major expansion of live device telemetry — speed, proximity, fault detection, and more.

### New
- **Speed** — real-time forward speed in m/s
- **Odometry** — total distance traveled by each wheel
- **Positioning Confidence** — how confident the device is in its GPS/odometry position (0–1)
- **Rain Sensor** — raw reading from the rain detection sensor
- **Chute Angle** — snow chute direction; only appears when the Snow Blower head is attached
- **Proximity** (left, center, right) — ultrasonic obstacle detection distances; 9999 = clear
- **Head Gyro Pitch / Roll** — head attachment angle (disabled by default, useful for diagnostics)
- **Impact** — fires when the robot detects a collision
- **Motor Fault** (left, right) — fires when a drive motor reports an error
- **Wheel Fault** (left, right) — fires when a wheel reports a fault
- **Radar Fault** — fires when the obstacle radar reports a fault
- **Power Fault** — fires when the device reports a power issue

### Changed
- Head-specific sensors (e.g. Chute Angle) automatically show as unavailable when the wrong head is attached

---

## [0.4.7] - 2026-05-30

More plan progress details, and the Plan selector now shows what's actually running.

### New
- **Plan Progress** — completion percentage of the current plan (0–100%)
- **Remaining Plan Area** — area still to be covered (m²)
- **Estimated Time Remaining** — device estimate of time left in the plan
- **Plan Elapsed Time** — how long the current plan has been running
- **Total Plan Area** — total area of the current plan (m²)
- **Total Plan Time** — estimated total duration of the plan

### Fixed
- **Plan Select** was showing *unknown* while a plan was running — it now shows the active plan name
- **Current Plan** sensor now automatically updates after plan completion, without needing to press *Refresh Plans* manually

---

## [0.4.6] - 2026-05-30

Know what your Yarbo is doing and how much it's done.

### New
- **Current Plan** — the name of the plan currently running (e.g. "South Front")
- **Completed Plan Area** — area covered so far in the current plan run (m²)
- **Plan Battery Consumption** — battery percentage used during the current run

### Fixed
- **Plan Select** now shows the active plan name while a plan is running instead of showing *unknown*

---

## [0.4.5] - 2026-05-30

Clearer sensor names and a diagnostic attribute for the charging sensor.

### Fixed
- The *Charging* sensor was renamed to **Active Charge** to avoid confusion with *Recharging Status*, which also uses "Charging" as a state value
- The **Active Charge** sensor now exposes its raw underlying value as an attribute, useful for diagnosing when the threshold should trigger

---

## [0.4.4] - 2026-05-30

Cleaner shutdowns — no more error messages when restarting Home Assistant.

### Fixed
- Home Assistant no longer logs `Event loop is closed` errors from the Yarbo integration when HA restarts

---

## [0.4.3] - 2026-05-30

Internal reliability and startup improvements.

### Fixed
- HA was logging blocking I/O warnings at startup caused by the integration loading the SDK on the event loop — resolved
- Volume entity now correctly reports its value as a percentage in all cases

---

## [0.4.2] - 2026-05-30

Startup warning eliminated.

### Fixed
- HA was logging blocking I/O warnings at startup when the integration loaded device data — resolved

---

## [0.4.1] - 2026-05-30

### Fixed
- An error was logged at every startup because the `set_nogozone_enabled` service was missing its definition file — fixed

---

## [0.4.0] - 2026-05-30

**Breaking change** — re-installation required if upgrading from 0.3.x.

### Changed
- Integration renamed from `yarbo` to `yarbo_bg` to avoid conflict with any official Yarbo integration that may be added to Home Assistant in the future
- The integration now appears in HACS and HA as **Yarbo BG**
- Existing installs must remove the old integration and re-add **Yarbo BG** — entity IDs will change

---

## [0.3.2] - 2026-05-29

Initial release of this fork with test infrastructure, map visualization, and plan management features.
