# Yarbo Monitoring Dashboard

Single-device monitoring dashboard for the `yarbo_bg` Home Assistant integration.

## Prerequisites

1. `yarbo_bg` integration installed and configured with at least one device.
2. Device serial number (SN) — visible in **Settings → Devices & Services → Yarbo BG → device name**.

## Setup

### 1. Install ha-map-card (HACS)

The map section requires `ha-map-card` from HACS ([github.com/nathan-gs/ha-map-card](https://github.com/nathan-gs/ha-map-card)).

1. Open HACS → Frontend → search "ha-map-card" → install **Map Card** by Nathan Brodin.
2. Reload browser cache (Ctrl+Shift+R).

### 2. Enable the Plan Path entity

`sensor.<SN>_plan_path` is disabled by default.

1. **Settings → Devices & Services → Yarbo BG → your device → entities**.
2. Find **Plan Path**, click it, toggle **Enable**.

### 3. Import the dashboard

1. Open the contents of `yarbo-monitoring.yaml` in a text editor. Find-replace every occurrence of
   `<DEVICE_SN>` with your device serial number (e.g. `YB123456`).
2. In HA: **Settings → Dashboards → Add Dashboard** (the + button). Give it a title (e.g. "Yarbo")
   and a URL path (e.g. `yarbo`). Click **Create**.
3. Open the new dashboard, then click the **pencil icon** (Edit dashboard) in the top-right.
4. Click the **three-dot menu → Raw configuration editor**.
5. Select all the existing content and replace it with the edited YAML from step 1. Click **Save**.

## Entity IDs

All entities use the pattern `<domain>.<DEVICE_SN>_<slug>`.
The serial number is shown in the device name in Settings → Devices & Services.
