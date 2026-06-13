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
