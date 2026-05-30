# Changelog

All notable changes to this project will be documented in this file.

---

## [0.4.9] - 2026-05-30

### Fixed
- Odometry L/R sensors: `TOTAL_INCREASING` → `MEASUREMENT` (device resets on restart; prior class corrupted HA long-term statistics)
- Fault binary sensors: replaced `bool(val)` with type-safe `_fault()` helper — `bool("0") == True` was incorrect; non-numeric payloads now treated as no-fault
- `power_fault` sensor: guard `int(val)` with `isinstance` check
- `available()` on head-type-gated sensors: guard `int(head_type)` conversion
- Coordinator: stamp `_last_planning_status[sn] = 5` before scheduling plan-list fetch to prevent duplicate requests from concurrent MQTT callbacks
- Coordinator: reset `_last_planning_status[sn]` on device reconnect so plan completion fires correctly after a reconnect

---

## [0.4.8] - 2026-05-30

### Added
**Sensors (raw telemetry):**
- `sensor.*_speed` — average forward speed (m/s)
- `sensor.*_odometry_left` / `*_odometry_right` — wheel odometry distance (m, `TOTAL_INCREASING`)
- `sensor.*_positioning_confidence` — fused odometry confidence (0–1)
- `sensor.*_rain_sensor` — rain sensor raw reading
- `sensor.*_chute_angle` — snow chute angle (°), **Snow Blower head only** (unavailable with other heads)
- `sensor.*_proximity_left` / `*_proximity_center` / `*_proximity_right` — ultrasonic distances (mm; 9999 = no obstacle)
- `sensor.*_head_gyro_pitch` / `*_head_gyro_roll` — head gyro angles (°), disabled by default

**Binary sensors (fault/status from `abnormal_msg`):**
- `binary_sensor.*_impact` — bump/collision detected (`vibration` device class)
- `binary_sensor.*_left_motor_fault` / `*_right_motor_fault` — motor faults (`problem` device class)
- `binary_sensor.*_left_wheel_fault` / `*_right_wheel_fault` — wheel faults
- `binary_sensor.*_radar_fault` — radar/obstacle detection fault
- `binary_sensor.*_power_fault` — power fault (fires when `power_fault > 0`)

### Changed
- Head-type gating: sensors unavailable when the wrong attachment is fitted (e.g. chute angle only for Snow Blower)

---

## [0.4.7] - 2026-05-30

### Added
- `sensor.*_plan_progress` — plan completion percentage (`actualCleanArea / totalCleanArea × 100`)
- `sensor.*_remaining_area` — area left to clean in current run (m²)
- `sensor.*_time_remaining` — estimated time remaining (seconds, `SensorDeviceClass.DURATION`)
- `sensor.*_elapsed_time` — time elapsed since plan start (seconds)
- `sensor.*_total_plan_area` — total area of the current plan (m²)
- `sensor.*_total_plan_time` — estimated total plan duration (seconds)

### Fixed
- Plan list auto-refreshes when `on_going_planning` transitions to `5` (Completed) — `Current Plan` sensor resolves correctly after next run without manual button press
- `Plan Select` and `Current Plan` survive HA restart while a plan is running (plan list re-fetched on completion)

---

## [0.4.6] - 2026-05-30

### Added
- `sensor.*_current_plan` — name of the currently running plan (e.g. "South Front"), matched from `plan_feedback.areaIds` against the plan list
- `sensor.*_clean_area` — area covered in the current run (m²)
- `sensor.*_battery_consumption` — battery % used in the current run

### Fixed
- `Plan Select` state now reflects the active plan name while a plan is running instead of showing `unknown`

---

## [0.4.5] - 2026-05-30

### Fixed
- Rename `Charging` binary sensor display name to `Active Charge` in code — avoids confusion with `Recharging Status` which also uses "Charging" as a state value. Fresh installs now get the correct name without a manual entity rename.
- Expose `battery_status_raw` attribute on the `Active Charge` binary sensor for threshold diagnosis.

---

## [0.4.4] - 2026-05-30

### Fixed
- Graceful HA shutdown: MQTT paho thread no longer throws `RuntimeError: Event loop is closed` during restart. All MQTT callbacks use a `_schedule_update()` helper that silently absorbs the error when the event loop is already closed.

---

## [0.4.3] - 2026-05-30

### Changed
- Move all lazy `yarbo_robot_sdk` imports to module level across every entity file — eliminates event-loop blocking I/O on first import (was causing HA startup warnings).
- Add public `coordinator.client` property; remove all direct accesses to `coordinator._client` from entity files.
- Add `pre-commit install` to `make setup` — ruff lint + format now runs on every commit automatically.

### Fixed
- `number.py`: `native_value` returned `int` in the volume-scale branch; now correctly returns `float`.
- `select.py`: remove inline `import logging as _logging`; use module-level `_LOGGER`.

---

## [0.4.2] - 2026-05-30

### Fixed
- Move `yarbo_robot_sdk` imports to module level in `coordinator.py` — eliminates blocking I/O warnings on HA startup (SDK was scanning device JSON files on the event loop).

---

## [0.4.1] - 2026-05-30

### Fixed
- Add missing `services.yaml` for the `set_nogozone_enabled` service (was causing an `ERROR` log on startup).

---

## [0.4.0] - 2026-05-30

### Changed
- **Breaking**: Renamed integration domain `yarbo` → `yarbo_bg` to avoid conflict with any upstream Yarbo integration in HA core. Existing installs must remove and re-add the integration.
- Updated `hacs.json` display name to "Yarbo BG".

### Added
- CI: `COMPONENT` and `HA_BRANCH` env vars in workflow — single place to update on rename or HA version bump.
- CI: pip download cache and HA core clone cache.
- CI: concurrency cancellation on PRs.
- CI: `--tb=short` on pytest.
- Release workflow: versioned zip artifact (`yarbo_bg-vX.Y.Z.zip`), zips only the component directory.
- Dev: `pre-commit` hooks (ruff lint + format).
- Security: pinned all dev dependencies to exact versions.

---

## [0.3.2] - 2026-05-29

### Added
- Test infrastructure and dev tooling (`make setup`, `make check`, pyright, ruff, bandit).
- Map and plan features from upstream PRs #2 and #7.
