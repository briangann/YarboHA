"""Constants for the Yarbo integration."""

DOMAIN = "yarbo"
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "select",
    "device_tracker",
    "button",
    "switch",
    "number",
]

# Config flow
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
# Config entry data keys
DATA_ACCESS_TOKEN = "access_token"
DATA_REFRESH_TOKEN = "refresh_token"

# Options
CONF_SELECTED_DEVICES = "selected_devices"

# Keep-awake policy: how aggressively HA renews the device wake-up command.
CONF_KEEP_AWAKE_MODE = "keep_awake_mode"
KEEP_AWAKE_ALWAYS = "always"
KEEP_AWAKE_DOCKED = "docked"
KEEP_AWAKE_OFF = "off"
KEEP_AWAKE_MODES = {
    KEEP_AWAKE_ALWAYS: "Always (device never sleeps)",
    KEEP_AWAKE_DOCKED: "Only while charging on the dock",
    KEEP_AWAKE_OFF: "Never (device sleeps on its own schedule)",
}
