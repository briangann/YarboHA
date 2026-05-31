# Yarbo Monitoring Dashboard

Single-device monitoring dashboard for the `yarbo_bg` Home Assistant integration.

## Prerequisites

1. `yarbo_bg` integration installed and configured with at least one device.
2. Device serial number (SN) — visible in **Settings → Devices & Services → Yarbo BG → device name**.

## Setup

### 1. Install HACS frontend cards

Two HACS frontend cards are required:

**ha-map-card** ([github.com/nathan-gs/ha-map-card](https://github.com/nathan-gs/ha-map-card)) — satellite map with GeoJSON overlay:
1. Open HACS → Frontend → search "ha-map-card" → install **Map Card** by Nathan Brodin.

**layout-card** ([github.com/thomasloven/lovelace-layout-card](https://github.com/thomasloven/lovelace-layout-card)) — CSS grid layout for the two-column view:
1. Open HACS → Frontend → search "layout-card" → install **layout-card** by Thomas Lovén.

After installing both, reload browser cache (Ctrl+Shift+R).

### 2. Enable the Plan Path entity (optional)

The plan path trace on the map is disabled by default. The map works without it. To enable:

1. **Settings → Devices & Services → Yarbo BG → your device → entities**.
2. Find **Plan Path**, click it, toggle **Enable**.
3. Uncomment the `plan_path` block in the map card section of the generated YAML before importing.

> **Warning:** If you include `sensor.<SN>_plan_path` in the map card while the entity is disabled,
> the entire map card will fail with a blank black screen. Enable the entity first.

### 3. Generate the dashboard YAML

Run `generate.py` from the repo root to produce a ready-to-paste YAML file:

```bash
python3 dashboards/generate.py YB123456
```

Replace `YB123456` with your actual serial number. The output is printed to stdout — pipe it to a
file if you prefer:

```bash
python3 dashboards/generate.py YB123456 -o my-yarbo-dashboard.yaml
```

### 4. Import into Home Assistant

1. In HA: **Settings → Dashboards → Add Dashboard** (the + button). Give it a title (e.g. "Yarbo")
   and a URL path (e.g. `yarbo`). Click **Create**.
2. Open the new dashboard, then click the **pencil icon** (Edit dashboard) in the top-right.
3. Click the **three-dot menu → Raw configuration editor**.
4. Select all the existing content, paste the generated YAML from step 3, and click **Save**.

## Entity IDs

All entities use the pattern `<domain>.<DEVICE_SN>_<slug>`.
The serial number is shown in the device name in Settings → Devices & Services.
