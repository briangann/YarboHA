# Changelog

What's new in each release of Yarbo BG.

---

## [0.4.11] - 2026-05-30

No more "Unknown" after restarting HA, and status labels that reflect what the robot is actually doing.

### Fixed
- **Unknown entities after restart** — the integration now remembers its last known state (plan list, device data, GPS reference, map data) and restores it immediately on the next startup. Entities that previously showed Unknown until the device responded to requests will now show their last values right away.
- **Auto Plan Status showed "Cleaning" regardless of head type** — now shows the correct verb: *Mowing* (mower / mower pro), *Blowing Snow* (snow blower), *Blowing* (blower), *Working* (smart cover or no head)

---

## [0.4.10] - 2026-05-30

Sensor names cleaned up — the Yarbo does mowing and snowblowing, not "cleaning".

### Changed
- Four sensors renamed to better reflect what the device actually does. Entity IDs are unchanged so existing automations and dashboards are not affected.
  - *Clean Area* → **Completed Plan Area**
  - *Battery Consumption* → **Plan Battery Consumption**
  - *Remaining Area* → **Remaining Plan Area**
  - *Elapsed Time* → **Plan Elapsed Time**

---

## [0.4.9] - 2026-05-30

Bug fixes identified during internal code review.

### Fixed
- **Odometry sensors** were using the wrong recorder category, which could corrupt long-term statistics in Home Assistant. Fixed.
- **Fault sensors** (motor, wheel, radar) could misread non-numeric values from the device as a fault. Fixed with a proper type check.
- **Current Plan** sensor now correctly updates after the device reconnects to the network — previously it could miss the first plan completion after a reconnect.
- Minor reliability improvement: plan list is only fetched once on plan completion, even if multiple status updates arrive simultaneously.

---

## [0.4.8] - 2026-05-30

Major expansion of live device telemetry — speed, proximity, fault detection, and more.

### New
- **Speed** — real-time forward speed in m/s
- **Odometry** — total distance traveled by each wheel
- **Positioning Confidence** — how confident the device is in its GPS/odometry position (0–1)
- **Rain Sensor** — raw reading from the rain detection sensor
- **Chute Angle** — snow chute direction; only appears when the Snow Blower head is attached
- **Proximity** (left, center, right) — ultrasonic obstacle detection distances; 9999 = clear
- **Head Gyro Pitch / Roll** — head attachment angle (disabled by default, useful for diagnostics)
- **Impact** — fires when the robot detects a collision
- **Motor Fault** (left, right) — fires when a drive motor reports an error
- **Wheel Fault** (left, right) — fires when a wheel reports a fault
- **Radar Fault** — fires when the obstacle radar reports a fault
- **Power Fault** — fires when the device reports a power issue

### Changed
- Head-specific sensors (e.g. Chute Angle) automatically show as unavailable when the wrong head is attached

---

## [0.4.7] - 2026-05-30

More plan progress details, and the Plan selector now shows what's actually running.

### New
- **Plan Progress** — completion percentage of the current plan (0–100%)
- **Remaining Plan Area** — area still to be covered (m²)
- **Estimated Time Remaining** — device estimate of time left in the plan
- **Plan Elapsed Time** — how long the current plan has been running
- **Total Plan Area** — total area of the current plan (m²)
- **Total Plan Time** — estimated total duration of the plan

### Fixed
- **Plan Select** was showing *unknown* while a plan was running — it now shows the active plan name
- **Current Plan** sensor now automatically updates after plan completion, without needing to press *Refresh Plans* manually

---

## [0.4.6] - 2026-05-30

Know what your Yarbo is doing and how much it's done.

### New
- **Current Plan** — the name of the plan currently running (e.g. "South Front")
- **Completed Plan Area** — area covered so far in the current plan run (m²)
- **Plan Battery Consumption** — battery percentage used during the current run

### Fixed
- **Plan Select** now shows the active plan name while a plan is running instead of showing *unknown*

---

## [0.4.5] - 2026-05-30

Clearer sensor names and a diagnostic attribute for the charging sensor.

### Fixed
- The *Charging* sensor was renamed to **Active Charge** to avoid confusion with *Recharging Status*, which also uses "Charging" as a state value
- The **Active Charge** sensor now exposes its raw underlying value as an attribute, useful for diagnosing when the threshold should trigger

---

## [0.4.4] - 2026-05-30

Cleaner shutdowns — no more error messages when restarting Home Assistant.

### Fixed
- Home Assistant no longer logs `Event loop is closed` errors from the Yarbo integration when HA restarts

---

## [0.4.3] - 2026-05-30

Internal reliability and startup improvements.

### Fixed
- HA was logging blocking I/O warnings at startup caused by the integration loading the SDK on the event loop — resolved
- Volume entity now correctly reports its value as a percentage in all cases

---

## [0.4.2] - 2026-05-30

Startup warning eliminated.

### Fixed
- HA was logging blocking I/O warnings at startup when the integration loaded device data — resolved

---

## [0.4.1] - 2026-05-30

### Fixed
- An error was logged at every startup because the `set_nogozone_enabled` service was missing its definition file — fixed

---

## [0.4.0] - 2026-05-30

**Breaking change** — re-installation required if upgrading from 0.3.x.

### Changed
- Integration renamed from `yarbo` to `yarbo_bg` to avoid conflict with any official Yarbo integration that may be added to Home Assistant in the future
- The integration now appears in HACS and HA as **Yarbo BG**
- Existing installs must remove the old integration and re-add **Yarbo BG** — entity IDs will change

---

## [0.3.2] - 2026-05-29

Initial release of this fork with test infrastructure, map visualization, and plan management features.
