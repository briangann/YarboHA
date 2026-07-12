# Session Log — Detailed

## 2026-06-13

### YarboHA upstream sync + test infrastructure
- Project-local venv now authoritative for lint/test tooling
- `make setup` simplified: removed HA core clone step
- Pyright config aligned with the project-local venv
- Required packages installed into the local environment for accurate LSP resolution
- Upstream sync brought in websocket GeoJSON, control gating, config-driven entities, coordinator persistence, keep-awake modes, typed dispatch, and battery sensors
- SDK bumped to `>=0.2.1`

### Bugs found and fixed
1. MQTT topic subscriptions were missing for plan feedback and cloud points
2. `number.py` had a wrong arg-count path for bound vs unbound publish
3. `_client is None` guards were missing in several command paths
4. Initial data fetch left entities unknown when offline
5. Button `async_press` swallowed errors
6. `SourceType` import path was wrong
7. `config_flow.py` had a type issue on title access

### Test infrastructure built
- 288 tests, 81% coverage, 0 pyright errors
- Pure logic tests for sensor extractors, binary thresholds, MQTT callbacks, coordinator invariants
- Integration tests via real HA fixture for entity registration, service calls, config flow, reauth, websocket API

### Pre-merge review findings
| # | Severity | File | Finding |
|---|---|---|---|
| 1 | 🔴 | `device_tracker.py` | Dedup guard removed → recorder GPS spam |
| 2 | 🔴 | `map_sensor.py` | `geojson` attribute removed → Lovelace map cards break |
| 3 | 🟡 | `button.py` | Wireless-charging check reversed |
| 4 | 🟡 | `select.py` | Plan select lost running-plan reflection |
| 5 | 🟡 | `__init__.py` | `set_nogozone_enabled` service removed without deprecation |
| 6 | 🟢 | `binary_sensor.py` | `extra_state_attributes` removed |
| 7 | 🟢 | `coordinator.py` | Plan-completion auto-refresh removed |

### Versioning clarification
- Upstream release tag and integration manifest version are different tracks
- The fork manifest version is what HACS uses

### Next session
- Address PR #23 blockers in order

### PR #23 blocker resolution + feature restoration
- Restored position dedup cache in `device_tracker.py`
- Fixed `map_sensor.py` dedup determinism with JSON serialization
- Restored raw telemetry attrs and fault binary sensors in `binary_sensor.py`
- Restored `plan_feedback` subscription and current-option reflection in `select.py`
- Restored nogo-zone service and raw map storage in `__init__.py` + `coordinator.py`
- Removed incorrect wireless-charging block in `button.py`
- Force-enabled SDK-disabled sensors in `sensor.py`
- Restored cloud point feedback and obstacle GeoJSON in `coordinator.py` + `websocket_api.py`
- 302 tests pass

### Open follow-ups
- Battery threshold SOC check in start-plan logic still needs live payload inspection
- Plan-completion auto-refresh removed upstream; documented, not restored

### Merge and release
- PR #23 merged to main
- Released `v0.5.2`
- CI passing: 302 tests, no lint errors, bandit clean
- CI workflow updated to use venv-based tooling
- Unawaited coroutine warning in tests fixed
- Battery threshold SOC check still needs live `get_device_msg` payload

### Dashboard branch and live migration
- Dashboard branch open and CI passing
- Rebased onto main (v0.5.2)
- Resolved CHANGELOG conflicts
- Added a GeoJSON sensor for map overlays
- Updated dashboard references to the new GeoJSON sensor
- Updated the dashboard README with the enable step and recorder exclusion note
- Deployed the integration update to the local HA instance
- Migrated the active Yarbo entry to the new integration version
- Repaired entity IDs after migration
- Dashboard confirmed working without console errors
- Area/user naming can alter entity IDs when using named entities
- Entity IDs are frozen after creation; renaming requires registry edits
- Dashboard working on the updated integration version
- PR still open for merge

## 2026-06-15

### Upstream lineage repair + audit
- Merged upstream lineage commits into `main` via `-s ours`
- Fork is now 0 commits behind upstream/main
- Full file-by-file audit confirmed nothing from upstream is missing in the fork
- Wireless-charging start-plan precondition remains removed because the robot autonomously undocks during wireless charging
- Wired charging remains a real physical blocker
- Battery threshold SOC check still needs live payloads

## 2026-06-20

### Blade metric fixes + power sensors
- Branch: `feat/blade-metrics` (branched from `main`)
- Commits: `5614355` and `94bf96f`
- Left/right blade current scaling fixed at ÷100
- Left/right blade power sensors added using live battery voltage with mV normalization
- Open questions captured in `docs/yarbo-questions.md`
- 30 new tests added for current scaling and power sensors

### Blade dashboard gauges + direction handling
- Branch: `feat/blade-metrics`
- Added blade power and RPM gauges to dashboard cards
- Fixed gauge type for the installed gauge card variant
- Left blade RPM returns absolute value; direction is exposed separately
- Left blade power uses absolute current so watts are always positive
- Gauge zones calibrated to measured operating data
- Verified locally; tests pass and pyright is clean
