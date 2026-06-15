# Session Log

## 2026-06-13 — Upstream Sync 0.3.3 + Test Infrastructure

### Branch
`feat/upstream-sync-0.3.3` → PR #23 (draft, do not merge)

### What was done
- Pulled in YarboInc upstream sync (commits b009815a + 37edd28b) → integration v0.5.1
- Fixed 3 real bugs found via pyright: `mqtt_subscribe` didn't exist (plan_feedback/cloud_points never subscribed), `BoundCoreModule.publish_command` wrong arg count, 7 `_client is None` guards missing
- Fixed bug #2: `_async_initial_data_fetch` left entities in "unknown" when all devices offline — now always calls `async_set_updated_data`
- Fixed button `async_press` swallowing `HomeAssistantError` — errors now surface in HA UI
- Full test infrastructure: 288 tests, 81% coverage, `pytest-homeassistant-custom-component`, real HA state machine tests, platform service call tests
- Proper pyright setup: `.venv` as authoritative env, SDK 0.2.1 installed (was 0.2.0), `make lint` = LSP
- AGENTS.md updated with current architecture, heartbeat timeout (90s not 15s), test coverage gaps

### Open blockers in PR #23
1. 🔴 `device_tracker.py` — `_maybe_write_state()` dedup guard removed → recorder GPS spam every 5s
2. 🔴 `map_sensor.py` — `geojson` attribute removed → existing Lovelace map cards break silently
3. 🟡 `button.py` — wireless-charging check reversed; needs device confirmation
4. 🟡 `select.py` — plan select no longer reflects running plan from `plan_feedback`
5. 🟡 `__init__.py` — `yarbo.set_nogozone_enabled` service removed without deprecation
6. 🟢 `binary_sensor.py` — `YarboOnlineBinarySensor.extra_state_attributes` removed; verify field coverage
7. 🟢 `coordinator.py` — plan-completion auto-refresh removed; add to release notes

### Next session: address blockers 1–5 in order

---

## 2026-06-13 (afternoon) — PR #23 Blocker Resolution + Feature Restoration

### Branch
`feat/upstream-sync-0.3.3` → PR #23 (description updated, all blockers resolved)

### What was done
- ✅ `device_tracker.py` — restored position dedup cache `_last_position`; ~30-60 recorder writes/min eliminated
- ✅ `map_sensor.py` — fixed `repr()` dedup → `json.dumps(sort_keys=True)`
- ✅ `binary_sensor.py` — restored 15 raw telemetry attrs on `YarboOnlineBinarySensor` (wheel speed, odometry, ultrasonic, gyro, etc.)
- ✅ `binary_sensor.py` — restored 7 fault binary sensors (`_YarboFaultBinarySensorBase`: impact, left/right motor, left/right wheel, radar, power)
- ✅ `select.py` — restored `plan_feedback` MQTT subscription + `current_option` reflects app-started plans (areaIds match), falls back to `get_selected_plan()`
- ✅ `__init__.py` + `coordinator.py` — restored `yarbo.set_nogozone_enabled` service + `async_set_nogozone_enabled()` + `_map_raw` storage
- ✅ `coordinator.py` — restored `cloud_points_feedback` MQTT subscription + `cloud_points` property
- ✅ `websocket_api.py` — `yarbo/map_zones` response now includes `obstacles_geojson` (GPS-projected dynamic obstacles)
- ✅ `button.py` — removed incorrect wireless-charging block (robot autonomously undocks)
- ✅ `sensor.py` — force-enabled all 16 SDK-disabled sensors (battery temps 1-6, voltage, current, charging_power, HaLow RSSI, obstacle, rain, odometry X/Y/phi, GPS sat count)
- 302 tests pass

### Open follow-ups (not blocking merge)
- Battery threshold SOC check in `YarboStartPlanButton` — field name TBD from device payload inspection (`BatteryMSG` has no min/max threshold fields in SDK; likely in REST `get_device_msg` response)
- `coordinator.py` — plan-completion auto-refresh (`on_going_planning == 5`) removed upstream; documented, not restored

---

## 2026-06-13 (late afternoon) — PR #23 merged, v0.5.2 released

### Status
- PR #23 merged to main at `55f8a35`
- Tagged and released `v0.5.2` → https://github.com/briangann/YarboHA/releases/tag/v0.5.2
- CI passing: 302 tests, 0 warnings, 0 lint errors, bandit clean

### Additional work done
- Restored 10 plan feedback sensors (`YarboCurrentPlanSensor`, clean area, battery consumption, progress, remaining area, time remaining, elapsed time, total area, total time, plan path GeoJSON)
- Added `keep — intentional` comments throughout codebase marking deliberate upstream divergences
- Created `CHANGELOG-dev.md` for internal review notes (AGENTS.md updated with convention)
- CI workflow updated: removed HA core clone, switched to `pytest-homeassistant-custom-component`; creates `.venv` to satisfy pyright; all action pins current
- Fixed `RuntimeWarning: coroutine was never awaited` in test mocks via `_close_background_task` side effect

### Open follow-ups
- Battery threshold SOC check in `YarboStartPlanButton` — inspect live device `get_device_msg` REST response for min/max SOC fields from "working preferences"

---

## 2026-06-13 (evening) — Dashboard branch rebase + live HA migration to yarbo v0.5.2

### Branch
`feat/yarbo-monitoring-dashboard` → PR #19 (open, CI passing)

### What was done
- Rebased `feat/yarbo-monitoring-dashboard` onto main (v0.5.2); resolved CHANGELOG conflicts; pushed
- Added `YarboMapGeoJsonSensor` — disabled by default, exposes `geojson` + `obstacles_geojson` in attributes for `ha-map-card` overlay (map_zones sensor no longer carries GeoJSON — moved to WebSocket in v0.5.1)
- Updated dashboard to reference `sensor.<SN>_map_geojson` instead of `map_zones`
- Updated `dashboards/README.md`: yarbo_bg → yarbo, added map_geojson enable step + recorder exclusion note
- Deployed to live HA on zeus — rsync to `/home/bgann/home-assistant/config/custom_components/yarbo/`
- Migrated live HA from `yarbo_bg` v0.4.13 → `yarbo` v0.5.2: added entry, deleted yarbo_bg
- Entity IDs changed from `24430102gm0w6421_*` → `barn_yarbo_*` (area BARN + device name Yarbo); fixed by clearing `name_by_user` + `area_id` from device registry and renaming 49 entity IDs in entity registry back to `24430102gm0w6421_*`
- Dashboard confirmed working: 0 console errors, map zones rendering, plan feedback live

### Open follow-ups
- PR #19 still open — merge when ready
- Battery threshold SOC check still pending
- Entity prefix lesson: `_attr_has_entity_name = True` + area assignment = `{area}_{device_name}_{entity}` prefix; cleared by setting `name_by_user=None` + `area_id=None` in device registry
