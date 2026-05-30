# SDK Gap Analysis

Audit of `yarbo-data-sdk==0.2.0` vs. `yarbo_bg` integration coverage.
Generated 2026-05-30. Re-run when SDK is updated.

---

## Control topics

| Topic | SDK method | Exposed | Notes |
|---|---|---|---|
| `set_working_state` | `mqtt_publish_command` | ✅ Select entity | |
| `start_plan` / `pause` / `resume` / `stop` | `mqtt_publish_command` | ✅ Buttons | |
| `cmd_recharge` | `mqtt_publish_command` | ✅ Button | |
| `set_sound_param` | `mqtt_publish_command` | ✅ Switch + Number | |
| `light_ctrl` | `mqtt_publish_command` | ✅ Switch | |
| `read_gps_ref` / `get_map` / `read_all_plan` / `get_device_msg` | SDK methods | ✅ Buttons | |
| `wireless_charging_cmd` | `mqtt_publish_command` | ❌ **Not exposed** | In device JSON, no entity wraps it |

---

## Status fields (sensors)

| Field | Exposed |
|---|---|
| Battery, Charging, Error Code, Network, RTK Signal | ✅ |
| Working State, Auto Plan Status, Pause Status, Recharging Status | ✅ |
| Head Type, Head Serial Number | ✅ |
| Sound Enabled, Headlight, Volume | ✅ |
| Position X/Y, Heading (disabled by default) | ✅ |
| `FieldDefinition.category` → `EntityCategory` mapping | ❌ **Not wired** — categories like `"status"`, `"head"`, `"position"` could map to `EntityCategory.DIAGNOSTIC` to declutter main UI |

---

## SDK client methods

| Method | Used | Notes |
|---|---|---|
| `login`, `restore_session`, `get_devices`, `mqtt_connect` | ✅ | |
| `subscribe_device_message`, `subscribe_heart_beat`, `subscribe_data_feedback` | ✅ | |
| `mqtt_publish_command`, `read_gps_ref`, `get_map`, `read_all_plan`, `get_device_msg` | ✅ | |
| `close` | ✅ | |
| `mqtt_unsubscribe()` | ❌ **Not used** | Subscriptions leak when devices are deselected via options flow |
| `request_with_feedback()` | ❌ **Not used** | Integration bypasses this with manual raw pub/sub for plan_feedback — SDK method handles timeout/retry more robustly |
| `mqtt_disconnect()` | ❌ **Not used directly** | Only `close()` called; likely fine if `close()` wraps it |
| `list_device_types()` | ❌ **Not used** | Low priority — diagnostic only |

---

## Device model fields

| Field | Used | Notes |
|---|---|---|
| `Device.sn`, `Device.type_id`, `Device.name` | ✅ | |
| `Device.model` | ❌ **Not exposed** | Available on device object, not surfaced as entity attribute |
| `Device.online` | ❌ **Not used** | REST-initial online state ignored; integration waits for first heartbeat instead |
| `Device.user_type` | ❌ **Not exposed** | Minor; unclear if useful |

---

## Exceptions

| Exception | Caught | Notes |
|---|---|---|
| `AuthenticationError`, `TokenExpiredError`, `YarboSDKError` | ✅ | |
| `MqttConnectionError` | ❌ **Not caught** | Falls through to generic `Exception` |
| `APIError` | ❌ **Not caught** | Falls through to generic `Exception` |

---

## Priority order

| # | Item | Effort | Value |
|---|---|---|---|
| 1 | `wireless_charging_cmd` button | Low — one button entity | Real missing feature |
| 2 | `mqtt_unsubscribe()` on device deselection | Medium | Fixes subscription leak |
| 3 | `MqttConnectionError` / `APIError` specific handling | Low | Better error messages in UI |
| 4 | `FieldDefinition.category` → `EntityCategory.DIAGNOSTIC` | Low | Cleaner HA entity list |
| 5 | Replace manual pub/sub with `request_with_feedback()` | Medium | More robust timeout/retry |
| 6 | `Device.online` initial state seeding | Low | Minor UX on first boot |
| 7 | `Device.model` as device registry attribute | Trivial | Cosmetic |
| 8 | `list_device_types()` diagnostic | Trivial | Dev tooling only |
