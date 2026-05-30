"""Prevent HA runtime imports from blocking unit tests.

custom_components/yarbo_bg/__init__.py imports HA at package load time.
Modules under test (coordinator.py, const.py, etc.) don't need HA
themselves, so mock the whole homeassistant namespace before collection.

Entity classes use multiple inheritance (e.g. CoordinatorEntity + SensorEntity).
Plain MagicMock objects cause metaclass conflicts when used as bases, so we
provide real (but minimal) stub base classes for the entity mix-ins.
"""

import sys
from unittest.mock import MagicMock


class _StubEntity:
    """Minimal HA entity stub — satisfies multiple-inheritance without metaclass conflict."""

    def __class_getitem__(cls, item):
        return cls

    _attr_has_entity_name: bool = False
    _attr_name: str | None = None
    _attr_unique_id: str | None = None
    _attr_entity_registry_enabled_default: bool = True

    def __init__(self, *args, **kwargs):
        pass

    @property
    def available(self) -> bool:
        return True

    def async_write_ha_state(self) -> None:
        pass


class _StubCoordinatorEntity(_StubEntity):
    def __init__(self, coordinator, *args, **kwargs):
        self.coordinator = coordinator


def _build_module_mock(**overrides):
    m = MagicMock()
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _mock_ha_modules() -> None:
    coordinator_mod = _build_module_mock(
        CoordinatorEntity=_StubCoordinatorEntity,
        DataUpdateCoordinator=_StubEntity,
        UpdateFailed=Exception,
    )
    sensor_mod = _build_module_mock(SensorEntity=_StubEntity)
    binary_sensor_mod = _build_module_mock(BinarySensorEntity=_StubEntity)
    button_mod = _build_module_mock(ButtonEntity=_StubEntity)
    select_mod = _build_module_mock(SelectEntity=_StubEntity)
    switch_mod = _build_module_mock(SwitchEntity=_StubEntity)
    number_mod = _build_module_mock(NumberEntity=_StubEntity, RestoreEntity=_StubEntity)
    device_tracker_mod = _build_module_mock(TrackerEntity=_StubEntity)

    module_map = {
        "homeassistant": MagicMock(),
        "homeassistant.components": MagicMock(),
        "homeassistant.components.binary_sensor": binary_sensor_mod,
        "homeassistant.components.button": button_mod,
        "homeassistant.components.device_tracker": device_tracker_mod,
        "homeassistant.components.device_tracker.config_entry": device_tracker_mod,
        "homeassistant.components.number": number_mod,
        "homeassistant.components.select": select_mod,
        "homeassistant.components.sensor": sensor_mod,
        "homeassistant.components.switch": switch_mod,
        "homeassistant.config_entries": MagicMock(),
        "homeassistant.const": MagicMock(),
        "homeassistant.core": MagicMock(),
        "homeassistant.exceptions": MagicMock(),
        "homeassistant.helpers": MagicMock(),
        "homeassistant.helpers.config_validation": MagicMock(),
        "homeassistant.helpers.device_registry": MagicMock(),
        "homeassistant.helpers.entity_platform": MagicMock(),
        "homeassistant.helpers.event": MagicMock(),
        "homeassistant.helpers.restore_state": MagicMock(),
        "homeassistant.helpers.update_coordinator": coordinator_mod,
    }
    for mod, mock in module_map.items():
        if mod not in sys.modules:
            sys.modules[mod] = mock


_mock_ha_modules()
