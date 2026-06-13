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
