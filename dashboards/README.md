# Yarbo Dashboards

Single-device dashboards for the `yarbo` Home Assistant integration.

## Available Dashboards

| File | Description | Best for |
|---|---|---|
| `yarbo-monitoring.yaml` | Full overview — map, plan details, faults, signal | General monitoring |
| `yarbo-active.yaml` | Active mow stats — battery, progress, blades, cells | Kiosk display during a mow |

## Kiosk Viewing (yarbo-active)

`yarbo-active` is designed for a **1920×1080 kiosk display with no scrolling**. At this resolution all 4 rows fit within the viewport.

### Browser kiosk setup

**Chrome/Chromium** (recommended):
```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --app=http://YOUR_HA_IP:8123/yarbo-active
```

**Home Assistant Companion App** (tablet/wall display):
- Settings → Companion App → Dashboard → set to `yarbo-active`
- Enable kiosk mode: add `?kiosk` to the URL — `http://YOUR_HA_IP:8123/yarbo-active?kiosk`
  (hides sidebar and header, leaving only dashboard content)

**Fully Kiosk Browser** (Android):
- Set start URL to `http://YOUR_HA_IP:8123/yarbo-active?kiosk`
- Enable "Keep Screen On" and "Motion Detection Wake"

### Viewport requirement

The layout is tuned for **1920×1080**. At narrower widths:
- Battery cell values may truncate
- Some glance card labels may be cut off

Minimum usable width: ~1280px. At 1280×800 the layout still fits without scrolling but values are shorter.

## Prerequisites

1. `yarbo` integration installed and configured with at least one device.
2. Device serial number (SN) — visible in **Settings → Devices & Services → Yarbo → your device**.

## Setup

### 1. Install HACS frontend cards

Two HACS frontend cards are required:

**ha-map-card** ([github.com/nathan-gs/ha-map-card](https://github.com/nathan-gs/ha-map-card)) — satellite map with GeoJSON overlay:
1. Open HACS → Frontend → search "ha-map-card" → install **Map Card** by Nathan Brodin.

**layout-card** ([github.com/thomasloven/lovelace-layout-card](https://github.com/thomasloven/lovelace-layout-card)) — CSS grid layout for the two-column view:
1. Open HACS → Frontend → search "layout-card" → install **layout-card** by Thomas Lovén.

After installing both, reload browser cache (Ctrl+Shift+R).

### 2. Enable the Map GeoJSON entity

The map zone and obstacle overlays require `sensor.<SN>_map_geojson` (disabled by default to avoid recorder bloat).

1. **Settings → Devices & Services → Yarbo → your device → entities**.
2. Find **Map GeoJSON**, click it, toggle **Enable**.

> **Recorder:** exclude this entity to prevent large GeoJSON payloads from filling the recorder database:
> ```yaml
> recorder:
>   exclude:
>     entities:
>       - sensor.24430102gm0w6421_map_geojson  # replace with your SN
> ```

### 3. Enable the Plan Path entity (optional)

The plan path trace on the map is disabled by default. The map works without it. To enable:

1. **Settings → Devices & Services → Yarbo → your device → entities**.
2. Find **Plan Path**, click it, toggle **Enable**.
3. Uncomment the `plan_path` block in the map card section of the generated YAML before importing.

> **Warning:** If you include `sensor.<SN>_plan_path` in the map card while the entity is disabled,
> the entire map card will fail with a blank black screen. Enable the entity first.

### 4. Generate the dashboard YAML

Run `generate.py` from the repo root to produce a ready-to-paste YAML file:

```bash
python3 dashboards/generate.py YB123456
```

Replace `YB123456` with your actual serial number. The output is printed to stdout — pipe it to a
file if you prefer:

```bash
python3 dashboards/generate.py YB123456 -o my-yarbo-dashboard.yaml
```

### 5. Import into Home Assistant

1. In HA: **Settings → Dashboards → Add Dashboard** (the + button). Give it a title (e.g. "Yarbo")
   and a URL path (e.g. `yarbo`). Click **Create**.
2. Open the new dashboard, then click the **pencil icon** (Edit dashboard) in the top-right.
3. Click the **three-dot menu → Raw configuration editor**.
4. Select all the existing content, paste the generated YAML from step 4, and click **Save**.

## Entity IDs

All entities use the pattern `<platform>.<lowercase_sn>_<slug>` — e.g. `sensor.24430102gm0w6421_battery`.
The serial number is shown in the device view in **Settings → Devices & Services → Yarbo**.
