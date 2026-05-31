# Yarbo Monitoring Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `dashboards/yarbo-monitoring.yaml` — an importable single-device monitoring Lovelace dashboard
with stat chips, GeoJSON map, plan progress, time/area stats, and fault indicators.

**Architecture:** Pure Lovelace YAML config with one HACS dependency (`lovelace-map-card`) for the GeoJSON map
overlay. No Python changes. Five card sections stacked in a single view. Placeholder `<DEVICE_SN>` throughout —
users do a find-replace with their serial number.

**Tech Stack:** Lovelace YAML, `lovelace-map-card` (HACS), Python YAML validation via stdlib.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `dashboards/yarbo-monitoring.yaml` | Create | Dashboard definition — all 5 card sections |
| `dashboards/README.md` | Create | Setup instructions: HACS install, enable plan_path entity, how to import |
| `CHANGELOG.md` | Modify | Add [Unreleased] Added entry |

---

## Task 1: Scaffold dashboard skeleton and README

**Files:**
- Create: `dashboards/yarbo-monitoring.yaml`
- Create: `dashboards/README.md`

- [ ] **Step 1: Create the dashboard skeleton**

Create `dashboards/yarbo-monitoring.yaml`:

```yaml
title: Yarbo Monitoring
views:
  - title: Overview
    path: yarbo-overview
    cards: []
```

- [ ] **Step 2: Create the README skeleton**

Create `dashboards/README.md`:

```markdown
# Yarbo Monitoring Dashboard

Single-device monitoring dashboard for the `yarbo_bg` Home Assistant integration.

## Prerequisites

1. `yarbo_bg` integration installed and configured with at least one device.
2. Device serial number (SN) — visible in **Settings → Devices & Services → Yarbo BG → device name**.

## Setup

### 1. Install lovelace-map-card (HACS)

The map section requires `lovelace-map-card` from HACS.

1. Open HACS → Frontend → search "map card" → install **Map Card** by Nathan Brodin.
2. Reload browser cache (Ctrl+Shift+R).

### 2. Enable the Plan Path entity

`sensor.<SN>_plan_path` is disabled by default.

1. **Settings → Devices & Services → Yarbo BG → your device → entities**.
2. Find **Plan Path**, click it, toggle **Enable**.

### 3. Import the dashboard

1. Open **Settings → Dashboards → Add Dashboard → From YAML**.
2. Paste the contents of `yarbo-monitoring.yaml`.
3. Find-replace `<DEVICE_SN>` with your device serial number (e.g. `YB123456`).

## Entity IDs

All entities use the pattern `<domain>.<DEVICE_SN>_<slug>`.
The serial number is shown in the device name in Settings → Devices & Services.
```

- [ ] **Step 3: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/yarbo-monitoring-dashboard
git add dashboards/yarbo-monitoring.yaml dashboards/README.md
git commit -m "feat: scaffold yarbo monitoring dashboard and README"
```

---

## Task 2: Section 1 — Stat chips (glance card)

**Files:**
- Modify: `dashboards/yarbo-monitoring.yaml`

- [ ] **Step 1: Replace `cards: []` with the glance card**

Replace the `cards: []` line in `dashboards/yarbo-monitoring.yaml` with:

```yaml
    cards:

      - type: glance
        title: Device Status
        entities:
          - entity: binary_sensor.<DEVICE_SN>_online
            name: Online
          - entity: sensor.<DEVICE_SN>_battery
            name: Battery
          - entity: sensor.<DEVICE_SN>_rtk_signal
            name: RTK Signal
          - entity: sensor.<DEVICE_SN>_network
            name: Network
```

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add dashboards/yarbo-monitoring.yaml
git commit -m "feat: add stat chips section to monitoring dashboard"
```

---

## Task 3: Section 2 — Map card (lovelace-map-card + GeoJSON)

**Files:**
- Modify: `dashboards/yarbo-monitoring.yaml`
- Modify: `dashboards/README.md` (verify HACS card name/install steps match actual card)

**Note on map card config:** `lovelace-map-card` GeoJSON attribute binding uses `geo_json_extra_sources`.
Verify the exact key names against the card's HACS page or GitHub README before committing. If the syntax
differs, update the YAML accordingly. The card repo is findable at hacs.xyz — search "map card".

- [ ] **Step 1: Append the map card after the glance card in `yarbo-monitoring.yaml`**

Add after the closing of the glance card (after the last `- entity:` block under Network):

```yaml

      - type: custom:map-card
        title: Location
        entities:
          - entity: device_tracker.<DEVICE_SN>_location
        geo_json_extra_sources:
          - entity: sensor.<DEVICE_SN>_map_zones
            attribute: geojson
          - entity: sensor.<DEVICE_SN>_map_zones
            attribute: obstacles_geojson
          - entity: sensor.<DEVICE_SN>_plan_path
            attribute: geojson
```

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 3: Verify map card GeoJSON config syntax**

Open the `lovelace-map-card` HACS page or GitHub README. Confirm:
- The card type string is `custom:map-card` (not `custom:lovelace-map-card` or similar).
- The key for GeoJSON layers from entity attributes is `geo_json_extra_sources`.
- The sub-keys are `entity` and `attribute`.

If any key names differ, update `yarbo-monitoring.yaml` to match and re-run Step 2.

Also update `dashboards/README.md` Step 1 ("Install lovelace-map-card") with the exact HACS card name
and author as shown on the HACS page.

- [ ] **Step 4: Commit**

```bash
git add dashboards/yarbo-monitoring.yaml dashboards/README.md
git commit -m "feat: add map card with GeoJSON zone and plan path overlay"
```

---

## Task 4: Section 3 — Plan progress (gauge + entities)

**Files:**
- Modify: `dashboards/yarbo-monitoring.yaml`

- [ ] **Step 1: Append gauge card**

Add after the map card block:

```yaml

      - type: gauge
        title: Plan Progress
        entity: sensor.<DEVICE_SN>_plan_progress
        min: 0
        max: 100
        unit: "%"
```

- [ ] **Step 2: Append plan details entities card**

Add after the gauge card:

```yaml

      - type: entities
        title: Plan Details
        entities:
          - entity: sensor.<DEVICE_SN>_current_plan
            name: Current Plan
          - entity: sensor.<DEVICE_SN>_auto_plan_status
            name: Plan Status
          - entity: sensor.<DEVICE_SN>_auto_plan_pause_status
            name: Pause Status
          - entity: sensor.<DEVICE_SN>_clean_area
            name: Area Done
          - entity: sensor.<DEVICE_SN>_remaining_area
            name: Remaining
          - entity: sensor.<DEVICE_SN>_estimated_time_remaining
            name: Time Remaining
```

- [ ] **Step 3: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 4: Commit**

```bash
git add dashboards/yarbo-monitoring.yaml
git commit -m "feat: add plan progress gauge and details section"
```

---

## Task 5: Section 4 — Time/area stats (glance)

**Files:**
- Modify: `dashboards/yarbo-monitoring.yaml`

- [ ] **Step 1: Append stats glance card**

Add after the plan details entities card:

```yaml

      - type: glance
        title: Plan Stats
        entities:
          - entity: sensor.<DEVICE_SN>_elapsed_time
            name: Elapsed
          - entity: sensor.<DEVICE_SN>_total_plan_time
            name: Total Time
          - entity: sensor.<DEVICE_SN>_total_plan_area
            name: Total Area
          - entity: sensor.<DEVICE_SN>_battery_consumption
            name: Battery Used
```

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add dashboards/yarbo-monitoring.yaml
git commit -m "feat: add time and area stats section"
```

---

## Task 6: Section 5 — Faults (entities) + CHANGELOG

**Files:**
- Modify: `dashboards/yarbo-monitoring.yaml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Append faults entities card**

Add after the plan stats glance card:

```yaml

      - type: entities
        title: Faults
        entities:
          - entity: sensor.<DEVICE_SN>_error_code
            name: Error Code
          - entity: binary_sensor.<DEVICE_SN>_impact
            name: Impact
          - entity: binary_sensor.<DEVICE_SN>_left_motor_fault
            name: Left Motor
          - entity: binary_sensor.<DEVICE_SN>_right_motor_fault
            name: Right Motor
          - entity: binary_sensor.<DEVICE_SN>_left_wheel_fault
            name: Left Wheel
          - entity: binary_sensor.<DEVICE_SN>_right_wheel_fault
            name: Right Wheel
          - entity: binary_sensor.<DEVICE_SN>_radar_fault
            name: Radar
          - entity: binary_sensor.<DEVICE_SN>_power_fault
            name: Power
```

- [ ] **Step 2: Validate complete dashboard YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"
```

Expected output: `YAML valid`

- [ ] **Step 3: Update CHANGELOG.md**

Add an `[Unreleased]` section (or append to existing one) at the top of the changelog:

```markdown
## [Unreleased]

### Added
- `dashboards/yarbo-monitoring.yaml`: single-device monitoring Lovelace dashboard with stat chips,
  GeoJSON map (zones + plan path + robot position via `lovelace-map-card`), plan progress gauge,
  time/area stats, and fault indicators.
- `dashboards/README.md`: setup instructions covering HACS card install, enabling the plan_path
  entity, and how to import and configure the dashboard.
```

- [ ] **Step 4: Commit**

```bash
git add dashboards/yarbo-monitoring.yaml CHANGELOG.md
git commit -m "feat: add faults section; complete monitoring dashboard"
```

---

## Verification Checklist

After all tasks complete, verify:

- [ ] `python3 -c "import yaml; yaml.safe_load(open('dashboards/yarbo-monitoring.yaml').read()); print('YAML valid')"` → `YAML valid`
- [ ] `dashboards/README.md` exists with HACS install, plan_path enable, and import steps
- [ ] `CHANGELOG.md` has an [Unreleased] entry for the dashboard
- [ ] All 5 sections present in YAML: glance (status), map, gauge, entities (plan), glance (stats), entities (faults)
- [ ] `<DEVICE_SN>` placeholder used consistently — no hardcoded serial numbers
- [ ] `make check` passes (no Python changes, but pre-commit hooks run on all staged files)
