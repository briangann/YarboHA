# Session Log — Detailed

## 2026-06-13 — YarboHA Upstream Sync + Test Infrastructure

### Branch / PR
- Branch: `feat/upstream-sync-0.3.3`
- PR #23: https://github.com/briangann/YarboHA/pull/23 (draft, blocked)

---

### Environment fixes
- `.venv` had `yarbo-data-sdk==0.2.0` (missing `client.core`, `client.device()`, etc.) — upgraded to `>=0.2.1`; stubs removed as unnecessary
- `pyrightconfig.json` now points at `.venv` (project-local); `make lint` uses `.venv/bin/pyright` explicitly; LSP and CLI now consistent
- `make setup` simplified: removed HA core clone step — `pytest-homeassistant-custom-component==0.13.339` installs HA 2026.6.3 as a proper dep
- `reportIncompatibleVariableOverride = false` added: HA 2026.6.3 changed `available`/`device_info`/`native_value` to `@cached_property`; standard override pattern is false positive
- `pyright` and `pytest` added to `~/venv` so LSP resolves imports correctly

---

### Upstream sync (commits b009815a + 37edd28b)
New in 0.3.3:
- `websocket_api.py` — GeoJSON served on-demand via WS (`yarbo/map_zones`), avoids 16KB recorder limit
- `entity_filters.py` — `control_matches_device()` suppresses wrong-head controls
- Config-driven sensor/binary_sensor (replaces ~20 individual classes)
- Coordinator: storage persistence, keep-awake modes (`CONF_KEEP_AWAKE_MODE`), `bound_device()` typed dispatch
- Battery: `battery_capacity` rescaling (firmware caps at 95% → rescaled to 100%), `charging_power` (V×I), new sensors for voltage/current/health/cell temps
- SDK bumped to `>=0.2.1` (`BoundDevice`, `_ensure_mqtt_for`, dual-broker; removes `mqtt_subscribe`)

---

### Bugs found and fixed (our additions on top of upstream)

1. **`mqtt_subscribe` doesn't exist in SDK 0.2.1** — plan_feedback and cloud_points topic subscriptions were silently failing (caught by `except Exception`). Fixed: `client._ensure_mqtt_for(sn).subscribe(topic, callback)`

2. **`number.py` wrong arg count** — `BoundCoreModule.publish_command(topic, payload)` vs `CoreModule.publish_command(sn, topic, payload, type_id)` — upstream ternary was calling bound path with 4 args (wrong). Fixed with separate if/else branches.

3. **7 `_client is None` guards** — `bound_device()` returns None when `_client is None`, then `else` branches accessed `_client` directly. Silent runtime failure. Added guards with `HomeAssistantError`.

4. **`_async_initial_data_fetch` left entities unknown** — `if self.data is not None: async_set_updated_data(self.data)` meant offline-at-startup devices left entities in "unknown" forever. Fixed: always `self.data = {}` if None, always call `async_set_updated_data`. Test: red→green.

5. **Button `async_press` swallowed errors** — all 5 command buttons had `except Exception` catching `HomeAssistantError`. User pressed button, nothing happened, no UI feedback. Fixed: `except HomeAssistantError: raise` + wrap SDK errors as `HomeAssistantError`.

6. **`SourceType` wrong import** — `homeassistant.components.device_tracker.config_entry` → `.entity`
7. **`config_flow.py` `str | None` title**, TypedDict safe access

---

### Test infrastructure built

**288 tests, 81% coverage, 0 pyright errors**

Test layers:
- Pure logic (sensor extractors, binary thresholds, MQTT callbacks, `_deep_merge` invariants, button safety, switch payloads, coordinator state)
- Integration via real `hass` fixture (full platform setup, state machine, service calls, config flow, reauth, websocket API)

Key test files:
- `test_platform_integration.py` — loads full integration into real HA; verifies entity registration, state transitions, service calls, unload
- `test_button_safety_checks.py` — all 18 precondition guards, now testing real raises (not silent swallow)
- `test_config_flow.py` — 100% coverage via real hass fixture
- `test_initial_data_fetch.py` — red→green test for the offline-device bug fix
- `test_coordinator_setup.py` — auth errors, MQTT failure, device filtering

Removed/trimmed:
- `test_coordinator.py` (duplicate of `test_coordinator_callbacks.py`)
- `test_integration_setup.py` (covered by platform integration test)
- `TestEntityWiring` trimmed to unique_id format only (changing breaks HA entity history)
- `TestPlanSelectOption` (duplicate of `test_select_async.py`)
- Mock service tests converted to real HA service calls in `test_platform_integration.py`

---

### Pre-merge review findings (documented in CHANGELOG [Unreleased] and PR #23)

| # | Severity | File | Finding |
|---|---|---|---|
| 1 | 🔴 | `device_tracker.py` | `_maybe_write_state()` removed → recorder GPS spam every ~5s |
| 2 | 🔴 | `map_sensor.py` | `geojson` attribute removed → silent break for Lovelace map cards |
| 3 | 🟡 | `button.py` | Wireless-charging check reversed; needs device confirmation |
| 4 | 🟡 | `select.py` | Plan select lost running-plan reflection from `plan_feedback` |
| 5 | 🟡 | `__init__.py` | `set_nogozone_enabled` service removed without deprecation |
| 6 | 🟢 | `binary_sensor.py` | `YarboOnlineBinarySensor.extra_state_attributes` removed |
| 7 | 🟢 | `coordinator.py` | Plan-completion auto-refresh removed |

---

### Versioning clarification
- Upstream GitHub release tag `v0.2.1` = SDK version, not integration version
- Upstream `manifest.json` version = `0.3.3`
- Our fork `manifest.json` version = `0.5.1` (what HACS uses)
- No conflict — two different numbering tracks

---

### Next session
Address PR #23 blockers 1–5 in order. Start with `device_tracker.py` recorder GPS spam (easiest — revert `_maybe_write_state`).

---

## 2026-06-13 (afternoon) — PR #23 Blocker Resolution + Feature Restoration

### Branch / PR
- Branch: `feat/upstream-sync-0.3.3`
- PR #23: https://github.com/briangann/YarboHA/pull/23 (description updated)
- Commits pushed: `971c03a..14ac065`

---

### Fixes applied

**device_tracker.py** (`971c03a`)
- Restored `_last_position` cache; `async_write_ha_state()` skipped when lat/lon/available unchanged
- Was writing ~30-60 recorder rows/min when device stationary

**map_sensor.py** (`971c03a`)
- `repr(self.extra_state_attributes)` → `json.dumps(..., sort_keys=True)` for deterministic dedup

**binary_sensor.py — 15 telemetry attrs** (`1805624`)
- Restored `extra_state_attributes` on `YarboOnlineBinarySensor`: wheel speed L/R/avg, dist L/R, odom confidence, impact, rain, gyro pitch/roll, chute angle, ultrasonic L/C/R, abnormal_msg

**select.py** (`546abde`, `fca0968`)
- Restored `plan_feedback` MQTT subscription (`snowbot/{sn}/device/plan_feedback`)
- `current_option`: checks `plan_feedback[sn].areaIds` → matches plan by areaIds → falls back to `get_selected_plan()` → falls back to `_attr_current_option`

**__init__.py + coordinator.py** (`c3a7a83`)
- Restored `yarbo.set_nogozone_enabled` service with full schema validation
- Restored `async_set_nogozone_enabled()`: reads `_map_raw`, mutates zone enable flag, publishes `snowbot/{sn}/app/save_nogozone` via `_ensure_mqtt_for(sn)` with firmware-aware encoding
- Added `_map_raw` storage alongside `_map_data` in `_async_fetch_map_data`

**button.py** (`04e9876`)
- Removed Check 4 (`BatteryMSG.status > 1` blocks plan start) — robot autonomously undocks from wireless charging

**sensor.py** (`854e899`, `37023c8`)
- `_FORCE_ENABLED` set overrides SDK `enabled_by_default=False` for 16 sensors:
  - BatteryMSG.temperature1-6, voltage, current
  - `__computed__.charging_power`, `halow_status.strength`
  - `StateMSG.obstacle`, `RunningStatusMSG.rain_sensor_data`
  - `CombinedOdom.x/y/phi`, `RTKMSG.sat_num`

**binary_sensor.py — fault sensors** (`eabf70f`)
- Restored `_YarboFaultBinarySensorBase` + 7 subclasses: Impact (VIBRATION), Left/Right Motor Fault, Left/Right Wheel Fault, Radar Fault, Power Fault
- Read from `abnormal_msg` / `RunningStatusMSG`; not in SDK field definitions

**coordinator.py + websocket_api.py** (`14ac065`)
- Restored `cloud_points_feedback` MQTT subscription + `_cloud_points` storage + `cloud_points` property
- `yarbo/map_zones` WebSocket response now includes `obstacles_geojson` (GPS-projected `tmp_barrier_points`)
- All restored subscriptions: INFO log on success, WARNING with feature impact on failure

---

### Open follow-ups
- **Battery threshold SOC check** in `YarboStartPlanButton`: user confirmed robot enforces min/max battery from "working preferences". Field not found in SDK JSON or MQTT push data — likely in REST `get_device_msg` response. Needs device payload inspection.
- **Plan-completion auto-refresh** (`on_going_planning == 5`): documented in CHANGELOG as removed upstream, not restored.

### Test count
302 tests pass (up from 288 at session start)

---

## 2026-06-13 (late afternoon) — Merged + Released v0.5.2

- PR #23 merged to main: `55f8a35`
- `v0.5.2` tagged and released: https://github.com/briangann/YarboHA/releases/tag/v0.5.2
- Final test count: 302 passed, 0 warnings, 0 pyright errors, bandit clean
- CI workflow fully updated: venv-based, no HA core clone, action pins current

### Late additions before merge
- Restored 10 plan feedback sensors (all read from `coordinator.plan_feedback`)
- `keep — intentional` comments added to all deliberate upstream divergences
- `CHANGELOG-dev.md` created; convention added to AGENTS.md §11
- `CHANGELOG.md` cleaned to user-facing release notes only
- `RuntimeWarning` from unawaited coroutine in tests fixed via `_close_background_task`

### Still open
- Battery threshold SOC check — field path unknown, needs live device `get_device_msg` inspection

---

## 2026-06-13 (evening) — Dashboard branch + Live HA Migration

### Branch / PR
- `feat/yarbo-monitoring-dashboard` → PR #19 (open)
- All work on this branch; no new merges to main

### Rebase
- Rebased onto main (v0.5.2); two CHANGELOG.md conflicts resolved
  - Dashboard Added section moved to `[Unreleased]` (not 0.5.1)
  - generate.py entry added to Unreleased
- Force-pushed `0b87f88`→`025bffb`

### YarboMapGeoJsonSensor (commit `025bffb`)
- New sensor in `map_sensor.py`; disabled by default
- `_attr_unique_id = f"{device.sn}_map_geojson"`
- `extra_state_attributes`: `geojson` (full GeoJSON from `coordinator.map_data`) + `obstacles_geojson` (GPS-projected cloud_points barriers)
- Dashboard updated: `sensor.<SN>_map_zones` → `sensor.<SN>_map_geojson` for GeoJSON overlays
- README: yarbo_bg → yarbo throughout; added step 2 (enable map_geojson + recorder exclude)

### Live HA Deployment
- rsync to zeus:/home/bgann/home-assistant/config/custom_components/yarbo/
- `docker restart homeassistant`
- Configured `yarbo` v0.5.2 entry: <account email>, selected 24430102GM0W6421, area=BARN, name="Yarbo"
- Deleted `yarbo_bg` v0.4.13 entry

### Entity ID problem and fix
- After migration, entity IDs became `barn_yarbo_*` (area BARN + device name "Yarbo")
- Old IDs were `24430102gm0w6421_*` (SN-based, no area/name prefix)
- Root cause: `_attr_has_entity_name = True` + `name_by_user = "Yarbo"` + `area_id = "barn"` → `{area}_{name_by_user}_{entity}` prefix
- Fix: set `name_by_user = None` + `area_id = None` in `core.device_registry`; renamed 49 entity IDs in `core.entity_registry` from `barn_yarbo_` → `24430102gm0w6421_`; restarted HA
- Result: entity IDs back to `24430102gm0w6421_*`, dashboard working, 0 console errors

### Key learnings
- HA entity IDs for `_attr_has_entity_name = True` entities: `{area}_{device_name}_{entity}` when area assigned; `{device_name}_{entity}` when no area; `{area}_{device_name}_{entity}` where device_name = `name_by_user` if set else SDK `device.name`
- SDK `device.name` = SN (`24430102GM0W6421`), so clearing `name_by_user` gives SN-based entity IDs
- Entity IDs are frozen at creation; must edit `core.entity_registry` directly to rename
- `generate.py` placeholder `<DEVICE_SN>` is correct for default installs with no area/name_by_user overrides

### Final state
- Dashboard fully working on yarbo v0.5.2: map zones, plan feedback (44.1%), device status, faults
- PR #19 open for merge; CI passing
