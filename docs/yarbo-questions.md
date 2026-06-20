# Questions to Ask Yarbo

Open questions about firmware behavior, MQTT payload encoding, and protocol details.
Add new items as they surface during development; remove or annotate when answered.

---

## MQTT Payload Encoding

**Q1: What do the `*_blade_motor_temp_status` values mean?**

Fields: `middle_blade_motor_temp_status`, `left_blade_motor_temp_status`, `right_blade_motor_temp_status`
(MQTT keys in `mower_head_info02`, `mower_head_info03`, `mower_head_info04`)

We receive an integer but have no spec for the mapping. Suspected:

| Value | Meaning |
|-------|---------|
| 0 | Normal |
| 1 | Warning |
| 2 | Fault / Overcurrent |

Confirmation needed so we can expose a proper enum state instead of a raw number.

---

**Q2: Does the left/right blade `motor_current` ÷100 scaling apply to the middle blade as well?**

We confirmed left and right blade motor current is a fixed-point integer (1 unit = 0.01 A)
based on observed values (50 displayed as 50 A, actually 0.50 A).
Is `middle_blade_motor_current` encoded the same way, or is it already in amps?

---

**Q3: Does `mower_head_info02` belong to the snow blower head, not the mower?**

The integration currently gates all `middle_blade_motor_*` sensors to mower head types (3=Mower,
5=Mower Pro) because they share the `_YarboMowerBladeSensor` base class. However, a physical
mower head has only two blades (left / right); there is no "middle blade" observed in the field.

Hypothesis: `mower_head_info02` is the snow blower's single impeller motor, and the
`middle_blade_motor_*` keys are misnamed from the firmware's perspective.

Needed: confirm which head type publishes `mower_head_info02`, and what the correct
`head_type` integer is (suspected: `1=Snow Blower`). If confirmed, the middle blade sensors
must be re-gated to `_HEAD_SNOW_BLOWER` and likely renamed.

---

**Q4: What does `*_blade_motor_over_current_info` encode?**

Fields: `middle_blade_motor_over_current_info`, `left_blade_motor_over_current_info`,
`right_blade_motor_over_current_info`
(MQTT keys in `mower_head_info02`, `mower_head_info03`, `mower_head_info04`)

The `_info` suffix suggests a status code rather than a measurement. We currently expose
the raw value as a number with no unit or device class. Needed:

- Is this a boolean flag (`0=OK`, `1=overcurrent tripped`)?
- Is it an integer fault code or a bitfield?

If boolean: should become a `binary_sensor`, not a `sensor`.
If an enum/code: needs a mapping table so HA can display a human-readable state.
