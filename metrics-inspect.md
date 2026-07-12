# Metrics to inspect for noise

Likely noisy metrics, based on the code paths and sensors exposed in `custom_components/yarbo/sensor.py`:

1. `BatteryMSG.current` via `charging_power`
   - already fixed to drop values outside `±800 W`
   - this was the one already discussed

2. `BatteryMSG.capacity` via `battery_capacity`
   - already rescaled/clipped
   - likely safe, but firmware oddities could still show up at the raw edge

3. `SoundMSG.volume` via `volume_scale`
   - expects `0.0–1.0` raw and maps to `0–100`
   - any bad upstream value would turn into a bogus percentage

4. `GpsMSG.rtk_status` via `rtk_signal`
   - not numeric noise, but it is a lossy mapping
   - anything other than `4` or `5` becomes `"Weak"`

5. `StateMSG.on_going_planning` via `planning_status`
   - unknown negative codes become `"Error"`
   - unknown positive codes become `None`

6. `StateMSG.on_going_recharging` via `recharging_status`
   - same idea as planning status

7. Raw telemetry currents / power sensors
   - `Left Wheel Current`
   - `Right Wheel Current`
   - `Brushless Motor Current`
   - `Push Pod Current`
   - `Chute Steering Current`
   - `Chute Current`
   - `Middle/Left/Right Blade Current`
   - `Middle/Left/Right Blade Power`
   - `Lift Motor Current`
   - these are the most likely next candidates for out-of-range filtering

8. Motion / IMU sensors
   - `Head Gyro Pitch`
   - `Head Gyro Roll`
   - `Body Gyro Pitch/Roll/Yaw`
   - `Body Acceleration X/Y/Z`
   - `Speed`
   - these can go wild if the upstream packet is malformed

9. Position / navigation sensors
   - `RTK Heading`
   - `RTK Latitude`
   - `RTK Longitude`
   - `RTK Altitude`
   - `Position Deviation`
   - good candidates for sanity bounds, especially latitude/longitude/deviation

10. Thermal sensors
   - `MOS Temperature`
   - `Motor NTC Temperature`
   - `Wireless Charge Temperature`
   - `Blade Temperature` sensors
   - worth filtering for impossible extremes

11. Wireless recharge sensors
   - `Wireless Charge Voltage`
   - `Wireless Charge Current`
   - live samples showed `4202.0 V` / `4186.0 V` and `51 A` / `53 A`, which is not physically plausible if interpreted literally
   - integration now normalizes fixed-point values by dividing by `1000` when the raw number is > 1000, and `charging_power` now drops values outside `±800 W`
   - keep inspecting these against raw MQTT payloads before adding more filters
