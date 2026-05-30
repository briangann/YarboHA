"""Prevent HA runtime imports from blocking unit tests.

custom_components/yarbo_bg/__init__.py imports HA at package load time.
Modules under test (coordinator.py, const.py, etc.) don't need HA
themselves, so mock the whole homeassistant namespace before collection.
"""

import sys
from unittest.mock import MagicMock


def _mock_ha_modules() -> None:
    ha_modules = [
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.binary_sensor",
        "homeassistant.components.button",
        "homeassistant.components.device_tracker",
        "homeassistant.components.device_tracker.config_entry",
        "homeassistant.components.number",
        "homeassistant.components.select",
        "homeassistant.components.sensor",
        "homeassistant.components.switch",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.exceptions",
        "homeassistant.helpers",
        "homeassistant.helpers.config_validation",
        "homeassistant.helpers.device_registry",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.event",
        "homeassistant.helpers.restore_state",
        "homeassistant.helpers.update_coordinator",
    ]
    for mod in ha_modules:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()


_mock_ha_modules()
