# Yarbo Grafana Dashboard — Metric Reference

## Dashboard panel summary

Dashboard: `Yarbo Mowing Overview` (folder `Yarbo`). Organized into three
collapsible rows, plus a device-selector template variable (`$device`) at the
top that filters every panel to one Yarbo unit.

### Live Status
- **Current Plan** — name of the plan currently running (e.g. "Back 40 East"), recovered from a numeric ID + value mapping since plan names can't export to Prometheus as text.
- **Battery Level** — current overall battery %, red/yellow/green thresholds.
- **Plan Progress** — % of the current plan's area completed so far.
- **Battery Used** — % of battery consumed since this plan run started.
- **Elapsed Time** — time since the current plan started, `hh:mm:ss`.
- **Time Remaining** — device's own ETA to finish the plan, `hh:mm:ss`.
- **Device State** — "Mowing" or "Charging", from the `active_charge` binary sensor.

### Plan & Battery Trends
- **Plan Area** — Completed / Remaining / Total area (ft²) over time; three lines converging as the plan progresses.
- **Plan Duration** — Elapsed / Remaining / Total time over the plan run.
- **Distance Traveled** — cumulative left/right wheel odometry (meters).
- **Battery Use per Minute** — % battery consumed per minute, live trend.
- **Battery Use per Sqft** — % battery consumed per square foot mowed, live trend (efficiency metric — should flatten out as the run stabilizes).
- **Battery vs Progress (Over Time)** — Battery Consumed % and Plan Progress % plotted on the same time axis; if they diverge, the mower is burning battery faster or slower than the physical progress it's making.
- **Battery vs Progress (Correlation)** — same two values as an X-Y scatter (progress on X, battery on Y) instead of against time — shows the actual relationship, not just parallel trends.
- **Battery Drain Rate** — instantaneous %/min drain, `-deriv()` of battery level. Inherently noisy near zero; used for visual trend only, not for predictions (see "Derived formulas" — predictions use the stable session average instead).

### Battery Predictions
- **Plan Time vs Battery Time** — overlays "Plan Time Remaining" against "Battery Time to Low Threshold," both in minutes. If the battery line dips below the plan line, the mower will hit low battery before finishing.
- **Battery Countdown** — live `hh:mm:ss` clock counting down to the low-battery threshold. Shows "Calculating…" while charging or when the drain signal is too weak to estimate.
- **Battery Margin** — minutes of slack between finishing the plan and hitting low battery; positive = plan finishes first, negative = will run out first.
- **Can Complete Plan?** — plain Yes/No: will the mower finish the remaining area before the battery hits the low threshold, at the current rate.
- **Area Left After Charge** — ft² that would still be unmowed if the mower stopped exactly at the low-battery threshold. `0` is a good result — it means the plan will fully complete first.
- **Battery Needed to Finish** — % of battery required to finish just the remaining area, at the current %-per-ft² efficiency.
- **Min. Redeploy Charge** — the battery % above which it's safe to send the mower back out after charging (needed-to-finish + low-battery reserve + travel reserve), as an alternative to waiting for the conservative 80% default.
- **Plan Countdown** — live `hh:mm:ss` clock counting down the device's own ETA to plan completion.
- **Battery Max Temp** — hottest of the 6 battery cell sensors, yellow/red thresholds at 45°C/55°C.
- **Battery Cell Temperatures** — all 6 individual cell temperatures over time, with the 45°C warning line drawn in.


Reference for the "Yarbo Mowing Overview" dashboard (Grafana Cloud, folder
`Yarbo`, UID `yarbo-mowing-overview`). Covers where the data comes from, how
it's exported, and every derived PromQL formula in use — so future panels
don't have to rediscover the gotchas below.

## Data path

```
Yarbo device --MQTT--> HA coordinator --entities--> HA "prometheus" integration
  (component: prometheus, configured in configuration.yaml)
  --scrape--> Grafana Alloy (job: integrations/hass) --remote_write--> Grafana Cloud (grafanacloud-prom)
```

- HA's `prometheus:` integration is a **scrape-only endpoint** (`/api/prometheus`)
  local to zeus. Something (Grafana Alloy) scrapes it and remote_writes into
  Grafana Cloud — confirmed already running under job `integrations/hass`.
- **Non-numeric (string) sensor states are silently dropped.** Plan names,
  enum-type status sensors (e.g. `auto_plan_status`, values like "Heading to
  Area"), and any text state never reach Prometheus — only numeric states do.
  Workaround used here: add a numeric sibling sensor and map the number back
  to text in Grafana via `mappings` (see "Current Plan Id" below). This is the
  same trick needed for any future text-state sensor you want in Grafana.

## HA → Prometheus metric name mapping

HA's exporter names metrics by domain + unit, not by entity name:

| HA domain / unit | Prometheus metric |
|---|---|
| `sensor` with `%` unit | `homeassistant_sensor_unit_percent` |
| `sensor` with `battery` device_class | `homeassistant_sensor_battery_percent` |
| `sensor` with area unit (ft²) | `homeassistant_sensor_unit_ftu0xb2` (yes, really — `ft²` gets mangled) |
| `sensor` with distance unit (m) | `homeassistant_sensor_unit_m` |
| `sensor` with `duration` device_class, unit `s` | `homeassistant_sensor_duration_s` |
| `sensor` with `temperature` in the *entity id* | `homeassistant_sensor_temperature` (always Celsius, see below) |
| `sensor` with no unit / plain number | `homeassistant_sensor_state` |
| `binary_sensor` | `homeassistant_binary_sensor_state` (1/0) |
| `input_number` | **not exported** — see workaround below |
| any domain, string state | **not exported** (no numeric gauge at all) |

The actual metric identity (which device/sensor) is a label, not part of the
metric name: `entity="sensor.<sn>_<name>"`. There is no separate "device"
label — if you need to group by device in PromQL, regex it out of `entity`
with `label_replace`.

Temperature note: `configuration.yaml` has a `prometheus.component_config_glob`
override forcing `sensor.*_temperature*` to `override_metric: sensor_temperature`
— this is why cell temps export as plain Celsius regardless of HA's display
unit (°F in the UI, °C in Prometheus). Don't assume unit parity between HA and
Prometheus for any metric that has such an override.

### `input_number` doesn't export — use a template sensor mirror

Needed for the low-battery/redeploy/travel-reserve thresholds (see below).
`input_number` entities do NOT appear in HA's Prometheus exporter at all
(checked directly — no `homeassistant_input_number_state` metric exists).
Fix: add a plain template `sensor` in `configuration.yaml` that just mirrors
`states('input_number.x')`, and export *that* instead:

```yaml
template:
  - sensor:
      - name: "Yarbo Low Battery Percent"
        unit_of_measurement: "%"
        state: "{{ states('input_number.yarbo_low_battery_percent') }}"
```

## Configurable thresholds (HA helpers, not hardcoded numbers)

Defined in `configuration.yaml` on zeus as `input_number` helpers, editable at
**Settings → Devices & Services → Helpers** without touching code or the
dashboard:

| Helper | Default | Mirror sensor (for Prometheus) | Purpose |
|---|---|---|---|
| `input_number.yarbo_low_battery_percent` | 15% | `sensor.yarbo_low_battery_percent` | Battery floor before mower must return to charge |
| `input_number.yarbo_redeploy_battery_percent` | 80% | `sensor.yarbo_redeploy_battery_percent` | Conservative "fully charged, safe to send back out" default |
| `input_number.yarbo_travel_reserve_percent` | 5% | `sensor.yarbo_travel_reserve_percent` | Extra battery buffer for the return trip to the mow site (not accounted for by the finish-the-plan calc alone) |

**Never hardcode these values in a panel query.** Always reference the mirror
sensor via `on(instance) homeassistant_sensor_unit_percent{entity="sensor.yarbo_..."}`.

## Custom sensors added to the integration (not stock SDK fields)

Added in `custom_components/yarbo/sensor.py` specifically to support Grafana
export (raw MQTT/plan_feedback duration fields come back as *formatted
strings* like "24m 26s", which Prometheus drops):

| Sensor | Entity ID suffix | Why |
|---|---|---|
| `YarboTimeRemainingSecondsSensor` | `_estimated_time_remaining_seconds` | Numeric sibling of `Estimated Time Remaining` (string) |
| `YarboElapsedTimeSecondsSensor` | `_elapsed_time_seconds` | Numeric sibling of `Plan Elapsed Time` (string) |
| `YarboTotalPlanTimeSecondsSensor` | `_total_plan_time_seconds` | Numeric sibling of `Total Plan Time` (string) |
| `YarboCurrentPlanIdSensor` | `_current_plan_id` | Numeric plan ID (matches `plan_feedback.areaIds` against `plan_data`, same logic as `YarboCurrentPlanSensor`) — lets Grafana show the plan **name** via a value mapping, since the string name itself can't export |

Each of these carries the plan name as an `extra_state_attributes["name"]` for
HA-side use, but that attribute is *not* visible to Prometheus — only the
`Current Plan` panel's value mapping (see below) recovers the name in Grafana.

## Grafana panel gotchas (apply to any new panel)

1. **Binary ops across different entities need `on(instance)`.** Two metrics
   for different entities never share a full label set (different `entity`,
   `friendly_name`, `__name__`), so `A - B` silently returns empty unless you
   write `A - on(instance) B`. This bit us repeatedly — always add `on(instance)`
   the moment a formula combines two different sensors. Nested binary ops need
   it on *every* division/subtraction, not just the outermost one.

2. **Stat panels default to a 6-hour range-reduce ("last non-null"), not the
   current instant value.** This caused stale/wrong-looking numbers (e.g. "0
   ft² left" when the real current answer was "Charging"). Fix: set
   `"instant": true` on every stat panel's target. Time series panels should
   stay as range queries (that's the point of a trend line).

3. **`plan_feedback` (and everything derived from it — area, plan name,
   consumption, elapsed time) resets to empty on every HA restart.** It's
   MQTT-push-only with no REST fallback, and only repopulates once the mower
   is actively running a plan again. Wrap these metrics in
   `last_over_time(metric[6h])` so panels hold the last known value through a
   restart or an idle/charging gap instead of going blank.

4. **Point-in-time `deriv()` on noisy telemetry is unreliable for
   predictions.** Early attempts computed "time to low battery" from
   `deriv(battery_percent[30m])`, which is dominated by noise near zero and
   gives nonsense results (saw both "243 days" and a bogus "charging" state
   while actively mowing). Fixed by using the **stable session average**
   instead: `plan_battery_consumption% / (plan_elapsed_time_seconds / 60)` —
   this is a cumulative average over the whole mow run, not an instantaneous
   slope, and matches the existing "Battery Use per Minute" panel's number.

5. **Gate on the real state sensor, not an inferred one.** Don't infer
   "charging" from drain-rate sign — use `binary_sensor.<sn>_active_charge`
   (exports as 1/0) directly: `... and on(instance)
   (homeassistant_binary_sensor_state{entity="binary_sensor.${device}_active_charge"} == 0)`.
   Also see the "Device State" panel (Mowing/Charging) built the same way.

6. **`clamp_min(x, epsilon)` to avoid division-by-zero silently produces
   absurd results** (e.g. dividing by 0.0001 turns a small numerator into a
   huge number). Prefer filtering with a real threshold (`... > 0.02`) so an
   unreliable/near-zero rate returns *no data* (handled via a panel's
   `fieldConfig.defaults.noValue` message) rather than a fabricated number.

## Derived formulas (as used in the dashboard, `${device}` = template variable)

Let:
- `LOW` = `on(instance) homeassistant_sensor_unit_percent{entity="sensor.yarbo_low_battery_percent"}`
- `TRAVEL` = `on(instance) homeassistant_sensor_unit_percent{entity="sensor.yarbo_travel_reserve_percent"}`
- `BATTERY` = `homeassistant_sensor_battery_percent{entity="sensor.${device}_battery"}`
- `NOT_CHARGING` = `on(instance) (homeassistant_binary_sensor_state{entity="binary_sensor.${device}_active_charge"} == 0)`
- `AVG_RATE` (%/min, stable session average) = `homeassistant_sensor_unit_percent{entity="sensor.${device}_plan_battery_consumption"} / on(instance) (homeassistant_sensor_duration_s{entity="sensor.${device}_plan_elapsed_time_seconds"} / 60)`
- `PLAN_REMAINING_MIN` = `on(instance) (homeassistant_sensor_duration_s{entity="sensor.${device}_estimated_time_remaining_seconds"} / 60)`
- `REMAINING_AREA` = `last_over_time(homeassistant_sensor_unit_ftu0xb2{entity="sensor.${device}_remaining_plan_area"}[6h])`
- `COMPLETED_AREA` = `last_over_time(homeassistant_sensor_unit_ftu0xb2{entity="sensor.${device}_completed_plan_area"}[6h])`
- `ELAPSED_MIN` = `last_over_time(homeassistant_sensor_duration_s{entity="sensor.${device}_plan_elapsed_time_seconds"}[6h]) / 60`
- `COVERAGE_RATE` (ft²/min) = `COMPLETED_AREA / on(instance) ELAPSED_MIN`

Then:

- **Time to Low Battery (min)** = `(((BATTERY - LOW) / on(instance) AVG_RATE) and NOT_CHARGING)`
  — empty ("Charging"/"Calculating…") while charging or when consumption data isn't available yet.

- **Battery Countdown** (seconds, for `dtdhms` display) = `Time to Low Battery * 60`

- **Battery Margin** (min, + = plan finishes first) = `Time to Low Battery - PLAN_REMAINING_MIN`

- **Can Complete Plan?** (boolean) = `Time to Low Battery >= bool PLAN_REMAINING_MIN`
  — mapped `1` → "Yes" (green), `0` → "No" (red).

- **Area Left After Charge** (ft²) = `clamp_min(REMAINING_AREA - on(instance) (COVERAGE_RATE * on(instance) Time to Low Battery), 0)`
  — how much area will still be unmowed when the mower has to stop for the
  low-battery threshold. `0` means the plan will fully complete first (good
  news, not a bug — verify against `REMAINING_AREA` before assuming it's wrong).

- **Battery % Needed to Finish Remaining Plan** = `REMAINING_AREA * on(instance) (homeassistant_sensor_unit_percent{entity="sensor.${device}_plan_battery_consumption"} / on(instance) COMPLETED_AREA)`
  (i.e. remaining area × current %-per-ft² efficiency)

- **Minimum Charge to Redeploy** = `(Battery % Needed to Finish Remaining Plan + LOW) + TRAVEL`
  — the point above which it's safe to send the mower back out, instead of
  blindly waiting for `yarbo_redeploy_battery_percent` (80% default).

- **Battery Efficiency, % per minute** = `homeassistant_sensor_unit_percent{...plan_battery_consumption} / on(instance) (homeassistant_sensor_duration_s{...plan_elapsed_time_seconds} / 60)` — this *is* `AVG_RATE` above; it's also drawn directly as its own time series panel.

- **Battery Efficiency, % per sqft** = `homeassistant_sensor_unit_percent{...plan_battery_consumption} / on(instance) homeassistant_sensor_unit_ftu0xb2{...completed_plan_area}`

- **Device State (Mowing/Charging)** = `homeassistant_binary_sensor_state{entity="binary_sensor.${device}_active_charge"}`, mapped `1` → "Charging" (blue), `0` → "Mowing" (green).

## Template variable

`$device` — query variable, `label_values(homeassistant_sensor_unit_percent{entity=~".*_plan_battery_consumption"}, entity)`,
regex `/sensor\.(.*)_plan_battery_consumption/` to extract just the serial.
**Set `refresh: 1`** (on dashboard load) — `refresh: 2` (on time-range change
only) leaves `$device` unresolved until the user touches the time picker,
which looks exactly like every panel being broken.

## Known limitations / not yet solved

- No true X-Y correlation of "battery vs. distance/area" independent of time
  — the "correlation" panel plots two time series against each other via the
  XY Chart panel (core plugin, must be **enabled** — it ships disabled by
  default on Grafana Cloud: `POST /api/plugins/xychart/settings {"enabled":true}`).
- Drain-rate noise near zero can still cause brief flicker between a real
  number and "Calculating…" right at a mowing/charging state transition —
  acceptable given the alternative (fabricated numbers) is worse.
- Plan name mapping (`Current Plan Id` → text) is a **static snapshot**, taken
  2026-08-19. If plans are renamed/added/removed in the Yarbo app, update the
  value mapping on the "Current Plan" panel by hand — there's no live sync.
