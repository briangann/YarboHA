"""Tests for entity_filters.control_matches_device.

All four decision branches:
  1. No compatible_head_types on ctrl_def → always True (universal control)
  2. Coordinator has no data → False
  3. Device SN not in coordinator data → False
  4. HeadMsg.head_type in compatible list → True / not in → False
  5. head_type non-numeric → False
"""

from unittest.mock import MagicMock

from custom_components.yarbo.entity_filters import control_matches_device

SN = "SN001"


def _coord(device_data=None):
    c = MagicMock()
    c.data = {SN: device_data} if device_data is not None else None
    return c


def _device(sn=SN):
    d = MagicMock()
    d.sn = sn
    return d


def _ctrl(compatible_head_types=None):
    c = MagicMock(spec=[])
    if compatible_head_types is not None:
        c.compatible_head_types = compatible_head_types
    # spec=[] means getattr raises AttributeError → getattr(ctrl_def, ..., None) returns None
    return c


class TestNoHeadFilter:
    """Controls with no compatible_head_types apply to every device."""

    def test_no_attribute_matches_all(self):
        ctrl = _ctrl()  # no compatible_head_types attr
        assert control_matches_device(_coord({}), _device(), ctrl) is True

    def test_empty_list_matches_all(self):
        ctrl = _ctrl(compatible_head_types=[])
        assert control_matches_device(_coord({}), _device(), ctrl) is True

    def test_none_value_matches_all(self):
        ctrl = _ctrl(compatible_head_types=None)
        assert control_matches_device(_coord({}), _device(), ctrl) is True


class TestNoData:
    """Returns False when coordinator has no data at all."""

    def test_no_coordinator_data(self):
        coord = _coord()  # data = None
        ctrl = _ctrl(compatible_head_types=[1, 2])
        assert control_matches_device(coord, _device(), ctrl) is False

    def test_empty_coordinator_data_dict(self):
        coord = MagicMock()
        coord.data = {}
        ctrl = _ctrl(compatible_head_types=[1])
        assert control_matches_device(coord, _device(), ctrl) is False


class TestHeadTypeMatch:
    """Checks head_type against compatible_head_types list."""

    def _make(self, head_type, compatible):
        coord = _coord({"HeadMsg": {"head_type": head_type}})
        return control_matches_device(coord, _device(), _ctrl(compatible))

    def test_matching_head_type(self):
        assert self._make(1, [1, 2]) is True

    def test_non_matching_head_type(self):
        assert self._make(3, [1, 2]) is False

    def test_string_int_coerced(self):
        assert self._make("1", [1, 2]) is True

    def test_non_numeric_string(self):
        assert self._make("mower", [1, 2]) is False

    def test_none_head_type(self):
        assert self._make(None, [1, 2]) is False

    def test_missing_head_msg(self):
        coord = _coord({})  # no HeadMsg key
        ctrl = _ctrl(compatible_head_types=[1])
        assert control_matches_device(coord, _device(), ctrl) is False
