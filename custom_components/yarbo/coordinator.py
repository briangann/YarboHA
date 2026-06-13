"""Data coordinator for Yarbo integration — MQTT push only, no polling."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from yarbo_robot_sdk import (
    AuthenticationError,
    TokenExpiredError,
    YarboClient,
    YarboSDKError,
)
from yarbo_robot_sdk.device_helpers import convert_map_to_geojson

from .const import (
    CONF_KEEP_AWAKE_MODE,
    CONF_SELECTED_DEVICES,
    DATA_ACCESS_TOKEN,
    DATA_REFRESH_TOKEN,
    DOMAIN,
    KEEP_AWAKE_ALWAYS,
    KEEP_AWAKE_DOCKED,
    KEEP_AWAKE_OFF,
)

_LOGGER = logging.getLogger(__name__)


def _deep_merge(target: dict, source: dict) -> bool:
    """Deep merge source into target, preserving existing nested dict values.

    For nested dicts, merges one level deep instead of replacing. Special keys
    '__online__' and 'HeartBeatMSG' in target are always preserved (not
    overwritten by device status pushes).

    Returns True if any value was added or changed, so callers can skip a
    coordinator refresh when a push carries nothing new.
    """
    changed = False
    for key, value in source.items():
        if key in ("__online__", "HeartBeatMSG"):
            continue  # Never overwrite these from device status
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            for k2, v2 in value.items():
                if k2 not in target[key] or target[key][k2] != v2:
                    target[key][k2] = v2
                    changed = True
        elif key not in target or target[key] != value:
            target[key] = value
            changed = True
    return changed


# Heartbeats arrive irregularly (~30s per spec, but observed 30–300s in the
# field), so the offline threshold must comfortably exceed the cadence or the
# device flaps online/offline. 90s ≈ 3× the spec interval.
HEARTBEAT_TIMEOUT_SECONDS = 90
HEARTBEAT_CHECK_INTERVAL = timedelta(seconds=5)
WAKEUP_RENEWAL_INTERVAL = timedelta(minutes=4)

# Persisted-map storage (survives restarts; re-fetched only on user refresh).
MAP_STORE_VERSION = 1
MAP_STORE_SAVE_DELAY = 5  # seconds, debounce writes

# Persisted user-standby preferences (so a restart doesn't wake devices the
# user explicitly put to sleep).
STANDBY_STORE_VERSION = 1


class YarboDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordinate data from Yarbo SDK.

    Data channel: MQTT push (real-time) only.
    Token refresh: handled on-demand by SDK RestClient (auto-refresh on 401).
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # No polling — MQTT is the only data channel
        )
        self.entry = entry
        self._client = None
        self.devices: list = []
        self._gps_refs: dict[str, dict] = {}
        self._map_data: dict[str, dict] = {}
        self._plan_data: dict[str, list[dict]] = {}
        self._last_heartbeat: dict[str, float] = {}
        self._user_standby: dict[str, bool] = {}
        # Online-recovery bookkeeping for the request/response data a device can
        # miss while offline (full DeviceMSG snapshot + Wi-Fi info). ``_inflight``
        # guards against overlapping fetches (a flapping device); ``_loaded``
        # records SNs fetched at least once, so a device that missed its startup
        # fetch (offline at the time) is retried when it first comes online.
        self._device_msg_inflight: set[str] = set()
        self._device_msg_loaded: set[str] = set()
        self._wifi_inflight: set[str] = set()
        self._wifi_loaded: set[str] = set()
        self._selected_plan: dict[str, int | None] = {}
        self._unsub_heartbeat_check: CALLBACK_TYPE | None = None
        self._unsub_wakeup_renewal: CALLBACK_TYPE | None = None
        # Persist last-known map + GPS reference so they survive restarts and
        # remain available while the device is offline. Re-fetched only on
        # explicit user refresh, never on a timer.
        self._map_store: Store = Store(
            hass, MAP_STORE_VERSION, f"{DOMAIN}_{entry.entry_id}_maps"
        )
        self._standby_store: Store = Store(
            hass, STANDBY_STORE_VERSION, f"{DOMAIN}_{entry.entry_id}_standby"
        )

    def _persist_maps(self) -> None:
        """Schedule a debounced save of the current map + GPS reference cache."""
        self._map_store.async_delay_save(
            lambda: {"map_data": self._map_data, "gps_refs": self._gps_refs},
            MAP_STORE_SAVE_DELAY,
        )

    async def _async_restore_maps(self) -> None:
        """Load persisted map + GPS reference cache into memory (best effort)."""
        try:
            stored = await self._map_store.async_load()
        except Exception as err:  # noqa: BLE001 - storage must never block setup
            _LOGGER.warning("Failed to restore persisted map data: %s", err)
            return
        if not stored:
            return
        self._map_data = stored.get("map_data") or {}
        self._gps_refs = stored.get("gps_refs") or {}
        _LOGGER.debug("Restored persisted maps for %d device(s)", len(self._map_data))

    async def async_setup(self) -> None:
        """Initialize SDK client, restore session, connect MQTT, subscribe."""
        # Show the last-known map immediately, before any device round-trip.
        await self._async_restore_maps()
        api_url = os.environ.get("YARBO_API_BASE_URL")

        def _create_client():
            return YarboClient(api_base_url=api_url) if api_url else YarboClient()

        client = await self.hass.async_add_executor_job(_create_client)
        self._client = client

        # Try to restore session from stored tokens
        token = self.entry.data.get(DATA_ACCESS_TOKEN)
        refresh_token = self.entry.data.get(DATA_REFRESH_TOKEN)

        try:
            if token and refresh_token:
                await self.hass.async_add_executor_job(
                    client.restore_session,
                    self.entry.data[CONF_EMAIL],
                    token,
                    refresh_token,
                )
            else:
                await self.hass.async_add_executor_job(
                    client.login,
                    self.entry.data[CONF_EMAIL],
                    self.entry.data[CONF_PASSWORD],
                )
        except (AuthenticationError, TokenExpiredError) as err:
            raise ConfigEntryAuthFailed from err

        # Get device list and filter by selection
        try:
            all_devices = await self.hass.async_add_executor_job(client.get_devices)
        except TokenExpiredError as err:
            raise ConfigEntryAuthFailed from err
        except YarboSDKError as err:
            raise UpdateFailed(f"Failed to get devices: {err}") from err

        selected_sns = set(self.entry.options.get(CONF_SELECTED_DEVICES, []))
        if selected_sns:
            self.devices = [d for d in all_devices if d.sn in selected_sns]
        else:
            self.devices = all_devices

        # Connect MQTT and subscribe to selected devices only
        try:
            await self.hass.async_add_executor_job(client.mqtt_connect)
            for device in self.devices:
                _LOGGER.info(
                    "Subscribing MQTT for %s (type_id=%s)",
                    device.sn,
                    device.type_id,
                )
                await self.hass.async_add_executor_job(
                    client.subscribe_device_message,
                    device.sn,
                    device.type_id,
                    self._on_device_status,
                )
                try:
                    await self.hass.async_add_executor_job(
                        client.subscribe_heart_beat,
                        device.sn,
                        device.type_id,
                        self._on_heart_beat,
                    )
                except YarboSDKError as err:
                    _LOGGER.warning(
                        "Heart beat subscription failed for %s: %s", device.sn, err
                    )
        except YarboSDKError as err:
            _LOGGER.warning("MQTT connection failed: %s", err)

        # Subscribe to data_feedback for selected devices
        for device in self.devices:
            try:
                await self.hass.async_add_executor_job(
                    client.subscribe_data_feedback,
                    device.sn,
                    device.type_id,
                    None,
                )
            except YarboSDKError as err:
                _LOGGER.warning(
                    "data_feedback subscription failed for %s: %s", device.sn, err
                )

        # Auto wake-up per the configured keep-awake policy. Restore persisted
        # standby preferences first so a restart doesn't wake devices the user
        # explicitly put to sleep. In "docked" mode no battery data has arrived
        # yet, so the initial wake-up is skipped; the renewal timer picks the
        # device up within one interval once charging status is known.
        await self._async_restore_standby()
        for device in self.devices:
            self._user_standby.setdefault(device.sn, False)
            if self._should_keep_awake(device.sn):
                await self._async_send_wakeup(device.sn, device.type_id)

        # Start heartbeat check timer (every 5s)
        self._unsub_heartbeat_check = async_track_time_interval(
            self.hass, self._async_check_heartbeats, HEARTBEAT_CHECK_INTERVAL
        )

        # Start wake-up renewal timer (every 4min)
        self._unsub_wakeup_renewal = async_track_time_interval(
            self.hass, self._async_renew_wakeup, WAKEUP_RENEWAL_INTERVAL
        )

        # Persist tokens (may have been refreshed during restore)
        self._update_stored_tokens()

        # Fetch initial per-device data in the background so setup returns fast.
        # Each request can block up to its timeout when a device is offline;
        # running them inline would stall (and risk cancelling) entry setup.
        self.entry.async_create_background_task(
            self.hass,
            self._async_initial_data_fetch(),
            name=f"{DOMAIN}_initial_fetch",
        )

    async def _async_initial_data_fetch(self) -> None:
        """Fetch initial snapshots for each device and publish to entities.

        DeviceMSG is fetched first because many entities are only available from
        the full snapshot; other command responses can be slower.

        Map data is intentionally NOT fetched here: it is restored from the
        persistent store on setup and only re-fetched from the device on an
        explicit user refresh (the "Refresh Map Data" button / card).
        """
        for device in self.devices:
            await self._async_fetch_device_msg(device.sn, device.type_id)
            await self._async_fetch_wifi_info(device.sn, device.type_id)
            await self._async_fetch_plans(device.sn, device.type_id)
            await self._async_fetch_gps_ref(device.sn, device.type_id)
        # Always notify entities after the initial fetch pass, even if every
        # device was offline and all fetches timed out. Without this, data stays
        # None and entities remain in "unknown" state indefinitely instead of
        # transitioning to "unavailable".
        if self.data is None:
            self.data = {}
        self.async_set_updated_data(self.data)

    # ---- MQTT callbacks ----

    def _on_device_status(self, topic: str, data: dict[str, Any]) -> None:
        """Handle MQTT real-time status push — deep merge into coordinator data.

        Real-time pushes may contain only a subset of fields within nested dicts
        (e.g. StateMSG with only changed fields). A top-level update() would
        overwrite the entire nested dict, losing fields from the initial snapshot.
        Deep merge preserves existing nested values while updating changed ones.
        """
        parts = topic.split("/")
        if len(parts) >= 2:
            sn = parts[1]
            if self.data is None:
                self.data = {}
            if sn not in self.data:
                self.data[sn] = {}
            # Only push a coordinator update (which re-runs every entity) when
            # the merge actually changed something; status pushes often repeat
            # identical fields, which would otherwise refresh entities ~constantly.
            if _deep_merge(self.data[sn], data):
                self.hass.loop.call_soon_threadsafe(
                    self.async_set_updated_data, self.data
                )

    def _on_heart_beat(self, topic: str, data: dict[str, Any]) -> None:
        """Handle heart beat push — update timestamp and online state.

        The device publishes a heartbeat every ~1-2s. Always refresh the
        liveness timestamp, but only push a coordinator update (which re-runs
        every entity) when something user-visible actually changed — the
        online state flipped or the HeartBeatMSG payload differs. This avoids a
        full entity refresh on every heartbeat.
        """
        parts = topic.split("/")
        if len(parts) >= 2:
            sn = parts[1]
            self._last_heartbeat[sn] = time.monotonic()
            if self.data is None:
                self.data = {}
            if sn not in self.data:
                self.data[sn] = {}

            was_online = self.data[sn].get("__online__")
            prev_payload = self.data[sn].get("HeartBeatMSG")
            self.data[sn]["HeartBeatMSG"] = data
            self.data[sn]["__online__"] = True

            # Re-fetch the request/response data a device may have missed while
            # offline — the full DeviceMSG snapshot and Wi-Fi info — when it
            # comes online. Triggered when we never loaded it (offline during the
            # startup fetch) or on an explicit offline→online transition (values
            # may be stale). Each fetch dedupes via its own in-flight guard, so
            # the steady-state case (already loaded, continuous heartbeats) is a
            # no-op. DeviceMSG and Wi-Fi are gated independently so a slow/missing
            # one doesn't suppress the other.
            came_online = was_online is False
            if (
                came_online or sn not in self._device_msg_loaded
            ) and sn not in self._device_msg_inflight:
                _LOGGER.info("[heart_beat] sn=%s online → re-fetch DeviceMSG", sn)
                self._schedule_refetch(
                    sn,
                    self._device_msg_inflight,
                    self.async_refresh_device_msg,
                    "refetch_device_msg",
                )
            if (
                came_online or sn not in self._wifi_loaded
            ) and sn not in self._wifi_inflight:
                _LOGGER.info("[heart_beat] sn=%s online → re-fetch Wi-Fi info", sn)
                self._schedule_refetch(
                    sn,
                    self._wifi_inflight,
                    self.async_refresh_wifi_info,
                    "refetch_wifi",
                )

            if was_online and prev_payload == data:
                return  # No user-visible change; skip the entity refresh.

            # Logged only when the payload changed (the dedup above), so this
            # stays quiet in steady state despite the 1-2s heartbeat cadence.
            _LOGGER.debug("[heart_beat] sn=%s → online, payload=%s", sn, data)
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    def _schedule_refetch(self, sn, inflight, refresh, label) -> None:
        """Schedule a one-shot online-recovery re-fetch for a device.

        Called from the MQTT heartbeat thread, so it hops onto the event loop to
        spawn the fetch. The underlying ``_async_fetch_*`` owns the in-flight
        guard, so overlapping triggers (a flapping device) collapse to a single
        fetch; the cheap ``inflight`` pre-check here just avoids spawning a task
        that would no-op, which also keeps the retry cadence at the fetch's
        timeout rather than every heartbeat.

        Args:
            sn: Device serial number.
            inflight: The resource's in-flight guard set, pre-checked here.
            refresh: Coroutine function ``(sn, type_id) -> Awaitable`` to run.
            label: Short tag for the background task name.
        """
        if sn in inflight:
            return
        device = next((d for d in self.devices if d.sn == sn), None)
        if device is None:
            return
        self.hass.loop.call_soon_threadsafe(
            lambda: self.entry.async_create_background_task(
                self.hass,
                refresh(sn, device.type_id),
                name=f"{DOMAIN}_{label}_{sn}",
            )
        )

    # ---- Heartbeat online detection ----

    async def _async_check_heartbeats(self, _now=None) -> None:
        """Check heartbeat timestamps and mark devices offline if timed out."""
        if self.data is None:
            return
        now = time.monotonic()
        changed = False
        for device in self.devices:
            sn = device.sn
            last = self._last_heartbeat.get(sn)
            was_online = self.data.get(sn, {}).get("__online__")
            if last is None or (now - last) > HEARTBEAT_TIMEOUT_SECONDS:
                if was_online is not False:
                    if sn not in self.data:
                        self.data[sn] = {}
                    self.data[sn]["__online__"] = False
                    _LOGGER.debug("[heartbeat_check] sn=%s → offline", sn)
                    changed = True
        if changed:
            self.async_set_updated_data(self.data)

    # ---- Auto wake-up and renewal ----

    def bound_device(self, sn: str):
        """Return a BoundYarboDevice for sn, with the current coordinator data snapshot.

        The bound device injects sn and type_id automatically so callers do not
        need to pass them.  Pass the current data so SDK-side head_type validation
        works when applicable.

        Falls back to raw client.mqtt_publish_command if the device is not found.
        """
        device = next((d for d in self.devices if d.sn == sn), None)
        if device is None or self._client is None:
            return None
        data = (self.data or {}).get(sn)
        return self._client.device(device, data=data)

    async def _async_send_wakeup(self, sn: str, type_id: str) -> None:
        """Send set_working_state {state:1, source:smart_home} to wake device."""
        if self._client is None:
            return
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                await self.hass.async_add_executor_job(bound.core.set_working_state, 1)
            else:
                # Fallback to raw API if device not in registry yet
                await self.hass.async_add_executor_job(
                    self._client.mqtt_publish_command,
                    sn,
                    type_id,
                    "set_working_state",
                    {"state": 1, "source": "smart_home"},
                )
            _LOGGER.debug("[wakeup] Sent wake-up to %s", sn)
        except Exception as err:
            _LOGGER.warning("Failed to send wake-up to %s: %s", sn, err)

    @property
    def keep_awake_mode(self) -> str:
        """Current keep-awake policy from the config entry options."""
        return self.entry.options.get(CONF_KEEP_AWAKE_MODE, KEEP_AWAKE_ALWAYS)

    def _is_charging(self, sn: str) -> bool:
        """Whether the device reports charging (BatteryMSG.status > 1)."""
        data = (self.data or {}).get(sn) or {}
        status = (data.get("BatteryMSG") or {}).get("status")
        return isinstance(status, (int, float)) and status > 1

    def _should_keep_awake(self, sn: str) -> bool:
        """Whether the keep-awake policy says to renew the wake-up for sn."""
        if self._user_standby.get(sn, False):
            return False
        mode = self.keep_awake_mode
        if mode == KEEP_AWAKE_OFF:
            return False
        if mode == KEEP_AWAKE_DOCKED:
            return self._is_charging(sn)
        return True

    async def _async_renew_wakeup(self, _now=None) -> None:
        """Renew wake-up per the keep-awake policy (called every 4min)."""
        for device in self.devices:
            if self._should_keep_awake(device.sn):
                await self._async_send_wakeup(device.sn, device.type_id)

    def set_user_standby(self, sn: str, is_standby: bool) -> None:
        """Mark whether the user has manually set a device to standby."""
        self._user_standby[sn] = is_standby
        _LOGGER.debug("[standby] sn=%s standby=%s", sn, is_standby)
        self._standby_store.async_delay_save(
            lambda: dict(self._user_standby), MAP_STORE_SAVE_DELAY
        )

    async def _async_restore_standby(self) -> None:
        """Load persisted user-standby preferences (best effort)."""
        try:
            stored = await self._standby_store.async_load()
        except Exception as err:  # noqa: BLE001 - storage must never block setup
            _LOGGER.warning("Failed to restore standby preferences: %s", err)
            return
        if stored:
            self._user_standby.update({sn: bool(v) for sn, v in stored.items()})
            _LOGGER.debug("Restored standby preferences: %s", self._user_standby)

    # ---- Plan list storage ----

    @property
    def plan_data(self) -> dict[str, list[dict]]:
        """Auto plan list per device: {sn: [{id, name, areaIds, ...}]}."""
        return self._plan_data

    def set_selected_plan(self, sn: str, plan_id: int | None) -> None:
        """Record the user's plan selection for Start Plan button."""
        self._selected_plan[sn] = plan_id

    def get_selected_plan(self, sn: str) -> int | None:
        """Get the currently selected plan ID for a device."""
        return self._selected_plan.get(sn)

    async def _async_fetch_plans(self, sn: str, type_id: str) -> None:
        """Fetch auto plan list for a device. Non-blocking on failure."""
        if self._client is None:
            return
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                result = await self.hass.async_add_executor_job(
                    bound.core.read_all_plan
                )
            else:
                result = await self.hass.async_add_executor_job(
                    self._client.read_all_plan, sn, type_id
                )
            plans = result.get("data", {}).get("data", [])
            self._plan_data[sn] = plans
            _LOGGER.info("Plans for %s: %d plans loaded", sn, len(plans))
        except TimeoutError:
            _LOGGER.warning(
                "Plan list request timed out for %s. "
                "Plan selection will be unavailable.",
                sn,
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch plans for %s: %s", sn, err)

    async def async_refresh_plans(self, sn: str, type_id: str) -> None:
        """Re-fetch plan list and trigger entity update."""
        await self._async_fetch_plans(sn, type_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    # ---- Full DeviceMSG snapshot ----

    async def _async_fetch_device_msg(self, sn: str, type_id: str) -> None:
        """Fetch full DeviceMSG snapshot and merge into coordinator data."""
        if self._client is None:
            return
        # Dedupe concurrent fetches (startup fetch vs. an online-transition
        # retry, or a mashed Refresh button) so we never run two 20s round-trips
        # for the same device at once.
        if sn in self._device_msg_inflight:
            return
        self._device_msg_inflight.add(sn)
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                result = await self.hass.async_add_executor_job(
                    bound.core.get_device_msg, 20.0
                )
            else:
                result = await self.hass.async_add_executor_job(
                    self._client.get_device_msg, sn, type_id, 20.0
                )
            msg_data = result.get("data", {})
            if self.data is None:
                self.data = {}
            if sn not in self.data:
                self.data[sn] = {}
            _deep_merge(self.data[sn], msg_data)
            self._device_msg_loaded.add(sn)
            _LOGGER.info(
                "Full DeviceMSG snapshot for %s loaded (%d top-level keys: %s)",
                sn,
                len(msg_data),
                list(msg_data.keys()),
            )
            # Debug: check specific fields
            state_msg = msg_data.get("StateMSG", {})
            _LOGGER.debug(
                "DeviceMSG snapshot StateMSG keys: %s, enable_sound=%s, volume=%s",
                list(state_msg.keys()) if isinstance(state_msg, dict) else "not-dict",
                state_msg.get("enable_sound") if isinstance(state_msg, dict) else "N/A",
                state_msg.get("volume") if isinstance(state_msg, dict) else "N/A",
            )
        except TimeoutError:
            _LOGGER.warning(
                "DeviceMSG request timed out for %s. Using real-time push data only.",
                sn,
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch DeviceMSG for %s: %s", sn, err)
        finally:
            self._device_msg_inflight.discard(sn)

    async def async_refresh_device_msg(self, sn: str, type_id: str) -> None:
        """Re-fetch full DeviceMSG snapshot and trigger entity update."""
        await self._async_fetch_device_msg(sn, type_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    # ---- Wi-Fi info ----

    async def _async_fetch_wifi_info(self, sn: str, type_id: str) -> None:
        """Fetch connected Wi-Fi info and merge it into coordinator data."""
        if self._client is None:
            return
        # Dedupe concurrent fetches (startup fetch vs. an online-transition
        # retry, or a mashed Refresh button) — same guard as DeviceMSG.
        if sn in self._wifi_inflight:
            return
        self._wifi_inflight.add(sn)
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                result = await self.hass.async_add_executor_job(
                    bound.core.get_connect_wifi_name, 30.0
                )
            else:
                result = await self.hass.async_add_executor_job(
                    self._client.get_connect_wifi_name, sn, type_id, 30.0
                )
            wifi_data = result.get("data", {})
            if self.data is None:
                self.data = {}
            if sn not in self.data:
                self.data[sn] = {}
            self.data[sn]["WifiInfo"] = wifi_data
            self._wifi_loaded.add(sn)
            _LOGGER.info(
                "Wi-Fi info for %s loaded (signal=%s)",
                sn,
                wifi_data.get("signal") if isinstance(wifi_data, dict) else None,
            )
        except TimeoutError:
            _LOGGER.warning(
                "Wi-Fi info request timed out for %s. Wi-Fi RSSI will be unavailable.",
                sn,
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch Wi-Fi info for %s: %s", sn, err)
        finally:
            self._wifi_inflight.discard(sn)

    async def async_refresh_wifi_info(self, sn: str, type_id: str) -> None:
        """Re-fetch connected Wi-Fi info and trigger entity update."""
        await self._async_fetch_wifi_info(sn, type_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    # ---- GPS reference ----

    @property
    def gps_refs(self) -> dict[str, dict]:
        """GPS reference origins per device."""
        return self._gps_refs

    async def _async_fetch_gps_ref(self, sn: str, type_id: str) -> None:
        """Fetch GPS reference origin for a device. Non-blocking on failure."""
        if self._client is None:
            return
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                result = await self.hass.async_add_executor_job(
                    bound.core.read_gps_ref, 30.0
                )
            else:
                result = await self.hass.async_add_executor_job(
                    self._client.read_gps_ref, sn, type_id, 30.0
                )
            gps_data = result.get("data", {})
            self._gps_refs[sn] = gps_data
            self._persist_maps()
            rtk_fix = gps_data.get("rtkFixType")
            if rtk_fix != 1:
                _LOGGER.warning(
                    "GPS reference for %s has rtkFixType=%s (not fixed). "
                    "Device tracker will be unavailable until device is "
                    "initialized via the Yarbo app.",
                    sn,
                    rtk_fix,
                )
            else:
                ref = gps_data.get("ref", {})
                _LOGGER.info(
                    "GPS reference for %s: lat=%s, lon=%s",
                    sn,
                    ref.get("latitude"),
                    ref.get("longitude"),
                )
        except TimeoutError:
            _LOGGER.warning(
                "GPS reference request timed out for %s. "
                "Device tracker will be unavailable.",
                sn,
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch GPS reference for %s: %s", sn, err)

    async def async_refresh_gps_ref(self, sn: str, type_id: str) -> None:
        """Re-fetch GPS reference origin and trigger entity update."""
        await self._async_fetch_gps_ref(sn, type_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    # ---- Map data ----

    @property
    def map_data(self) -> dict[str, dict]:
        """Map zone data per device: {sn: GeoJSON FeatureCollection}."""
        return self._map_data

    async def _async_fetch_map_data(self, sn: str, type_id: str) -> None:
        """Fetch map/zone data for a device. Non-blocking on failure."""
        if self._client is None:
            return
        try:
            bound = self.bound_device(sn)
            if bound is not None:
                result = await self.hass.async_add_executor_job(bound.core.get_map)
            else:
                result = await self.hass.async_add_executor_job(
                    self._client.get_map, sn, type_id
                )
            raw_data = result.get("data", {})
            # Some firmware returns the map payload as a JSON-encoded string
            # rather than an object; normalize it before conversion.
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data) if raw_data.strip() else {}
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Map data for %s: 'data' is a non-JSON string "
                        "(%r…); skipping this refresh.",
                        sn,
                        raw_data[:120],
                    )
                    return
            if not isinstance(raw_data, dict):
                _LOGGER.warning(
                    "Map data for %s: unexpected 'data' type %s; skipping. "
                    "Full response keys: %s",
                    sn,
                    type(raw_data).__name__,
                    list(result.keys()),
                )
                return
            fallback_ref = self._gps_refs.get(sn)
            geojson = convert_map_to_geojson(raw_data, fallback_ref)
            self._map_data[sn] = geojson
            self._persist_maps()
            feature_count = len(geojson.get("features", []))
            _LOGGER.info("Map data for %s: %d features loaded", sn, feature_count)
        except TimeoutError:
            _LOGGER.warning(
                "Map data request timed out for %s. Map zones will be unavailable.",
                sn,
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch map data for %s: %s", sn, err)

    async def async_refresh_map_data(self, sn: str, type_id: str) -> None:
        """Re-fetch map data and trigger entity update."""
        await self._async_fetch_map_data(sn, type_id)
        if self.data is not None:
            self.async_set_updated_data(self.data)

    # ---- Internal ----

    async def _async_update_data(self) -> dict[str, dict]:
        """No-op — MQTT is the sole data channel. Polling is disabled."""
        return self.data or {}

    def _update_stored_tokens(self) -> None:
        """Persist current tokens to config_entry if changed."""
        if self._client is None:
            return
        current_token = self._client.token
        current_refresh = self._client.refresh_token
        stored_token = self.entry.data.get(DATA_ACCESS_TOKEN)
        stored_refresh = self.entry.data.get(DATA_REFRESH_TOKEN)
        if current_token != stored_token or current_refresh != stored_refresh:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    DATA_ACCESS_TOKEN: current_token,
                    DATA_REFRESH_TOKEN: current_refresh,
                },
            )

    async def async_shutdown(self) -> None:
        """Clean up SDK client and timers on unload."""
        if self._unsub_heartbeat_check:
            self._unsub_heartbeat_check()
            self._unsub_heartbeat_check = None
        if self._unsub_wakeup_renewal:
            self._unsub_wakeup_renewal()
            self._unsub_wakeup_renewal = None
        if self._client:
            await self.hass.async_add_executor_job(self._client.close)
            self._client = None
