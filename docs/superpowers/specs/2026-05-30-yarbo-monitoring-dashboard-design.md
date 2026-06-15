# Yarbo Monitoring Dashboard — Design Spec

**Date:** 2026-05-30
**Scope:** Single-device, monitoring-only Lovelace YAML dashboard for the `yarbo_bg` HA integration.
**Output file:** `dashboards/yarbo-monitoring.yaml`

---

## Summary

A Lovelace dashboard that lets users watch a single Yarbo robot in real time: connectivity/battery
status, live map with zones and plan path, plan progress, time/area stats, and fault indicators.
No controls — read-only monitoring. Single HACS dependency (`lovelace-map-card`) required for the
GeoJSON map overlay.

---

## Decisions Made

| Question | Choice |
|---|---|
| Dashboard type | Lovelace YAML (importable) |
| Device scope | Single device |
| Purpose | Monitoring only (no controls) |
| Layout | C — stat chips → map → plan progress → time/area stats → fault row |
| Stat chips | Core 4: Online, Battery, RTK Signal, Network |
| Map content | Zones + plan path trace + robot position |
| Fault row | Yes — 7 fault sensors + error code |
| HACS dependencies | One: `lovelace-map-card` |

---

## Entity Reference

All entity IDs use `<DEVICE_SN>` as placeholder. Users replace with their device serial number
(e.g., `YB123456`).

### Section 1 — Stat Chips

| Entity | Card |
|---|---|
| `binary_sensor.<DEVICE_SN>_online` | `glance` |
| `sensor.<DEVICE_SN>_battery` | `glance` |
| `sensor.<DEVICE_SN>_rtk_signal` | `glance` |
| `sensor.<DEVICE_SN>_network` | `glance` |

### Section 2 — Map

| Entity / Attribute | Role |
|---|---|
| `device_tracker.<DEVICE_SN>_location` | Robot GPS position |
| `sensor.<DEVICE_SN>_map_zones` → attr `geojson` | Work zones + no-go zones GeoJSON |
| `sensor.<DEVICE_SN>_map_zones` → attr `obstacles_geojson` | Dynamic obstacles GeoJSON |
| `sensor.<DEVICE_SN>_plan_path` → attr `geojson` | Plan path trace GeoJSON |

**Card:** `custom:map-card` from HACS `lovelace-map-card`.
**Note:** `sensor.<DEVICE_SN>_plan_path` is disabled by default. Dashboard README must instruct
users to enable it in HA (Settings → Devices & Services → Yarbo → enable Plan Path entity).
**Note:** Exact YAML syntax for GeoJSON attribute binding must be verified against `lovelace-map-card`
docs during implementation — the config structure varies by card version.

### Section 3 — Plan Progress

Two built-in cards stacked:

**3a — Gauge** (`gauge` card):
- `sensor.<DEVICE_SN>_plan_progress` (0–100%)
- No severity thresholds — plain completion gauge; 100% = done = good, no warning states needed

**3b — Plan Details** (`entities` card):
- `sensor.<DEVICE_SN>_current_plan`
- `sensor.<DEVICE_SN>_auto_plan_status`
- `sensor.<DEVICE_SN>_auto_plan_pause_status`
- `sensor.<DEVICE_SN>_clean_area`
- `sensor.<DEVICE_SN>_remaining_area`
- `sensor.<DEVICE_SN>_estimated_time_remaining`

### Section 4 — Time/Area Stats

**Card:** `glance`

- `sensor.<DEVICE_SN>_elapsed_time`
- `sensor.<DEVICE_SN>_total_plan_time`
- `sensor.<DEVICE_SN>_total_plan_area`
- `sensor.<DEVICE_SN>_battery_consumption`

### Section 5 — Faults

**Card:** `entities`, title "Faults"

- `sensor.<DEVICE_SN>_error_code`
- `binary_sensor.<DEVICE_SN>_impact`
- `binary_sensor.<DEVICE_SN>_left_motor_fault`
- `binary_sensor.<DEVICE_SN>_right_motor_fault`
- `binary_sensor.<DEVICE_SN>_left_wheel_fault`
- `binary_sensor.<DEVICE_SN>_right_wheel_fault`
- `binary_sensor.<DEVICE_SN>_radar_fault`
- `binary_sensor.<DEVICE_SN>_power_fault`

---

## File Layout

```
dashboards/
  yarbo-monitoring.yaml   ← output file
  README.md               ← setup instructions (enable plan_path entity, install lovelace-map-card)
```

---

## HACS Dependency

| Card | HACS repo | Purpose |
|---|---|---|
| `lovelace-map-card` | verify at hacs.xyz during implementation | GeoJSON zone + path overlay on map |

Users must install this card via HACS before the dashboard loads correctly.

---

## Out of Scope

- Controls (plan select, start/pause/stop, return to charge)
- Multi-device layout
- Custom card development
- History graphs / statistics panels
