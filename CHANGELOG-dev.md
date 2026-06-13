# Developer Changelog

Internal notes on integration decisions, upstream sync reviews, and regression analysis.
User-facing release notes are in [CHANGELOG.md](CHANGELOG.md).

---

## [0.5.2 / 0.5.1] - 2026-06-13 — Upstream Sync 0.3.3 Review

### Upstream changes reviewed

Upstream commits `b009815a` + `37edd28b` (YarboInc → v0.5.1) removed:
- Config-driven `YarboConfigSensor` / `YarboConfigBinarySensor` replaced ~20 hardcoded subclasses
- Coordinator rewrite: HA `Store` persistence, keep-awake policy, typed `BoundDevice` SDK dispatch
- WebSocket map API (`yarbo/map_zones`) replaces GeoJSON in entity attributes (16 KB limit workaround)
- SDK bumped to `yarbo-data-sdk>=0.2.1` — adds `BoundDevice`, dual-broker MQTT, removes `mqtt_subscribe`

### Regressions found and fixed

| File | Issue | Fix | Commit |
|------|-------|-----|--------|
| `device_tracker.py` | Removed `_maybe_write_state()` dedup → ~30-60 recorder writes/min when parked | Restored `_last_position` cache | `971c03a` |
| `map_sensor.py` | `repr()` dedup non-deterministic on float dicts → writes every push | `json.dumps(sort_keys=True)` | `971c03a` |
| `binary_sensor.py` | 15 raw telemetry attrs removed from `YarboOnlineBinarySensor`, zero SDK coverage | Restored `extra_state_attributes` | `1805624` |
| `binary_sensor.py` | 7 fault sensors deleted (`_YarboFaultBinarySensorBase` + subclasses) | Restored all 7 | `eabf70f` |
| `sensor.py` | 10 plan feedback sensors deleted | Restored all 10 | `60fcbfe` |
| `select.py` | `plan_feedback` MQTT removed → select blind to app-started plans | Restored subscription + areaIds matching | `fca0968` |
| `__init__.py` | `yarbo.set_nogozone_enabled` removed without deprecation | Restored service + coordinator method + `_map_raw` | `c3a7a83` |
| `coordinator.py` | `cloud_points_feedback` subscription removed → no dynamic obstacles | Restored subscription + WebSocket overlay | `14ac065` |
| `button.py` | Wireless charging check reversed — now blocks plan start | Removed check; robot autonomously undocks | `04e9876` |
| `binary_sensor.py` | `Active Charge` name override removed → clashes with `Recharging Status` | Restored name override | `ce99244` |

### Decisions made this session

- **Wireless charging**: confirmed device autonomously undocks — NOT a blocker for plan start. Only wired (`rechargeState` 1 or 3) blocks.
- **`geojson` attribute removal**: accepted as upstream architectural decision (moved to WebSocket). No passthrough added.
- **Plan-completion auto-refresh** (`on_going_planning == 5`): removed upstream, not restored. Plan list requires manual refresh or HA restart.
- **Battery threshold SOC check**: user confirmed device enforces min/max from "working preferences". Field not found in SDK JSON or MQTT push data. Follow-up required — inspect `get_device_msg` REST response from a live device.

### Features added on top of upstream

- Force-enabled 16 SDK-disabled sensors (`_FORCE_ENABLED` in `sensor.py`): battery temps 1–6, voltage, current, charging power, HaLow RSSI, obstacle, rain, odometry X/Y/phi, GPS sat count.
- All restored subscriptions log INFO on success, WARNING with feature impact on failure.
- `keep — intentional` comments added throughout codebase to mark deliberate divergences from upstream.

### Upstream removals documented in CHANGELOG.md

- Plan-completion auto-refresh
- `yarbo.set_nogozone_enabled` (restored this session)
- 15 `YarboOnlineBinarySensor` attributes (restored this session)

---

## [0.5.1 / 0.5.0] - 2026-06-13 — Upstream Sync initial review

### Pyright bugs fixed (not upstream changes)

1. `mqtt_subscribe` didn't exist in SDK 0.2.1 — `plan_feedback` and `cloud_points` subscriptions silently failed; fixed using `client._ensure_mqtt_for(sn).subscribe(...)`
2. `BoundCoreModule.publish_command(topic, payload)` vs `CoreModule.publish_command(sn, topic, payload, type_id)` — upstream ternary passed wrong args to bound path
3. 7 `_client is None` guards missing in button, number, select, switch fallback branches
4. `_async_initial_data_fetch` left entities in "unknown" when all devices offline — always call `async_set_updated_data`
5. `button.async_press` swallowed `HomeAssistantError` — errors now surface in HA UI

### Infrastructure

- Migrated to `pytest-homeassistant-custom-component==0.13.339` (installs HA 2026.6.3 as dep)
- Removed HA core clone step from `make setup`
- `.venv` as authoritative pyright env; `make lint` = `make check` = LSP
- SDK upgraded to `>=0.2.1` (was `0.2.0`)
