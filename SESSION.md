# Session Log

## 2026-06-13

### Upstream Sync 0.3.3 + Test Infrastructure
- Pulled in YarboInc upstream sync (commits b009815a + 37edd28b) → integration v0.5.1
- Fixed 3 real bugs found via pyright: `mqtt_subscribe` didn't exist (plan_feedback/cloud_points never subscribed), `BoundCoreModule.publish_command` wrong arg count, 7 `_client is None` guards missing
- Fixed bug #2: `_async_initial_data_fetch` left entities in "unknown" when all devices offline — now always calls `async_set_updated_data`
- Fixed button `async_press` swallowing `HomeAssistantError` — errors now surface in HA UI
- Full test infrastructure: 288 tests, 81% coverage, `pytest-homeassistant-custom-component`, real HA state machine tests, platform service call tests
- Proper pyright setup: project-local venv as authoritative env, SDK 0.2.1 installed (was 0.2.0), `make lint` = LSP
- AGENTS.md updated with current architecture, heartbeat timeout (90s not 15s), test coverage gaps

### PR #23 blocker resolution and feature restoration
- Restored position dedup cache in `device_tracker.py`; eliminated recorder GPS spam
- Fixed `map_sensor.py` dedup determinism with JSON serialization
- Restored raw telemetry attrs and fault binary sensors in `binary_sensor.py`
- Restored `plan_feedback` subscription and current-option reflection in `select.py`
- Restored nogo-zone service and raw map storage in `__init__.py` + `coordinator.py`
- Removed incorrect wireless-charging block in `button.py`
- Force-enabled SDK-disabled sensors in `sensor.py`
- Restored cloud point feedback and obstacle GeoJSON in `coordinator.py` + `websocket_api.py`
- 302 tests pass

### PR #23 merge and release
- PR #23 merged to main at `55f8a35`
- Tagged and released `v0.5.2`
- CI passing: 302 tests, 0 warnings, 0 lint errors, bandit clean
- Restored 10 plan feedback sensors
- Added `keep — intentional` comments marking deliberate upstream divergences
- Created `CHANGELOG-dev.md` for internal review notes
- CI workflow updated to use `pytest-homeassistant-custom-component` and project-local venv
- Fixed `RuntimeWarning: coroutine was never awaited` in test mocks

### Dashboard branch and live migration
- Rebased dashboard branch onto main (v0.5.2); resolved CHANGELOG conflicts
- Added `YarboMapGeoJsonSensor` for map overlay GeoJSON
- Updated dashboard references to the new GeoJSON sensor
- Updated dashboard README with enable step and recorder exclusion note
- Migrated the active Yarbo entry to the new integration version
- Repaired entity IDs after migration
- Dashboard confirmed working without console errors

---

## 2026-06-15

### Upstream lineage repair and audit
- Merged upstream lineage commits into `main` via `-s ours`
- Fork is now 0 commits behind upstream/main
- Full file-by-file audit confirmed nothing from upstream is missing in the fork
- Wireless-charging start-plan precondition remains removed because the robot autonomously undocks during wireless charging
- Wired charging remains a real physical blocker

---

## 2026-06-20

### Blade metric fixes and dashboard gauges
- Fixed left/right blade current ÷100 scaling (firmware = fixed-point integer, 1 unit = 0.01 A)
- Added `YarboLeftBladePowerSensor` + `YarboRightBladePowerSensor` (P = V × I, live battery voltage with mV normalization)
- Added `docs/yarbo-questions.md` — open questions list for firmware team (Q1–Q4)
- Added TODO on middle blade section pending Q3 clarification
- 30 new tests in `tests/test_blade_current_scaling.py`; 0 pyright errors
- Added RPM gauges to dashboard for left/right blades
- Fixed gauge type for the installed gauge card variant
- Left blade RPM returns absolute value; direction is exposed separately
- Left blade power uses absolute current so watts are always positive
- Gauge zones calibrated to measured operating data
- Verified locally; tests pass and pyright is clean
