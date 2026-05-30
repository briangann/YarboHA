# Changelog

All notable changes to this project will be documented in this file.

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
