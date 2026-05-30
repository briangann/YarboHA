# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Home Assistant custom integration (HACS) for Yarbo Y Series robot devices. Python package at `custom_components/yarbo/`. Version tracked in `manifest.json`.

## Development setup

### Type checking

```bash
pyright custom_components/yarbo/
```

`pyrightconfig.json` points to `.venv` in the project root. Use the shared venv at `/Users/bgann/.venv` (Python 3.14) or create one:

```bash
uv venv --python 3.14
uv pip install pytest pytest-asyncio
```

### Tests

Unit tests run without a live HA instance — HA modules are mocked in `tests/conftest.py`:

```bash
/Users/bgann/.venv/bin/python -m pytest tests/ -v
```

### HA integration testing

1. Copy `custom_components/yarbo/` into your HA instance's `config/custom_components/` directory
2. Restart Home Assistant
3. Check logs at **Settings → System → Logs** or `home-assistant.log`

The SDK is an external PyPI package (`yarbo-data-sdk>=0.2.0` / import name `yarbo_robot_sdk`). Set `YARBO_API_BASE_URL` env var to override the default API endpoint during development.

## Architecture

### Data flow

**MQTT push only — no polling.** `update_interval=None` on the coordinator. Data arrives via two MQTT callbacks:

- `_on_device_status` — device telemetry pushes; deep-merged into `coordinator.data[sn]`
- `_on_heart_beat` — heartbeat pings; updates `coordinator.data[sn]["__online__"]` and `_last_heartbeat[sn]`

`_deep_merge()` in `coordinator.py` intentionally never overwrites `__online__` or `HeartBeatMSG` from device status pushes — these are heartbeat-only keys.

### Coordinator (`coordinator.py`)

`YarboDataUpdateCoordinator` owns everything:
- `self.data` — `{sn: {MQTT fields...}}` dict, the single source of truth for all entities
- `self._gps_refs`, `self._map_data`, `self._plan_data` — side-channel data fetched via REST, not MQTT
- `self._user_standby` — tracks whether user manually set device to standby (suppresses auto wake-up renewal)
- Timers: heartbeat check every 5s, wake-up renewal every 4min
- Session tokens persisted to config entry; SDK handles 401 auto-refresh

### Entity wiring

**Sensors** are configuration-driven: `get_field_definitions(device.type_id)` from the SDK returns field definitions; one `YarboConfigSensor` is created per field with `entity_type == "sensor"`. Field paths use dot notation (e.g. `StateMSG.battery`) resolved by `yarbo_robot_sdk.device_helpers.extract_field`.

Custom extractors in `YarboConfigSensor._extract_custom()` handle: `network_priority`, `volume_scale`, `rtk_signal`, `planning_status`, `recharging_status`.

**Map zone sensor** (`map_sensor.py`) exposes GeoJSON FeatureCollection in `extra_state_attributes["geojson"]`, used for HA map card zone overlays.

**Device tracker** (`device_tracker.py`) converts relative device position (X/Y meters from GPS reference origin) to absolute lat/lon using `self.coordinator.gps_refs[sn]`.

**Buttons** (`button.py`) — `YarboStartPlanButton` and `YarboRechargeButton` run multi-step safety precondition checks before issuing MQTT commands; raise `HomeAssistantError` with user-visible messages on failure.

### Config/Options flow

Two-step config flow: credentials → device multi-select. Device selection stored in `entry.options[CONF_SELECTED_DEVICES]`. Options change triggers full integration reload via `_async_options_updated`.

### Key constants

- `CONF_SELECTED_DEVICES` — list of device serial numbers in `entry.options`
- `DATA_ACCESS_TOKEN` / `DATA_REFRESH_TOKEN` — persisted in `entry.data`
- MQTT special keys: `__online__` (bool), `HeartBeatMSG` (last heartbeat payload)
- Heartbeat timeout: 15s; check interval: 5s; wake-up renewal: 4min
