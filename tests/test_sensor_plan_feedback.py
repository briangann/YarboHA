"""Tests for plan-feedback-derived sensors."""

import pytest
from unittest.mock import MagicMock

from custom_components.yarbo_bg.sensor import (
    YarboBatteryConsumptionSensor,
    YarboCleanAreaSensor,
    YarboCurrentPlanSensor,
    YarboElapsedTimeSensor,
    YarboPlanProgressSensor,
    YarboRemainingAreaSensor,
    YarboTimeRemainingSensor,
    YarboTotalPlanAreaSensor,
    YarboTotalPlanTimeSensor,
)

SN = "DEVICE_SN"


def _device():
    d = MagicMock()
    d.sn = SN
    return d


def _make(cls, plan_feedback=None, plan_data=None):
    sensor = object.__new__(cls)
    coord = MagicMock()
    coord.plan_feedback = {SN: plan_feedback or {}}
    coord.plan_data = {SN: plan_data or []}
    sensor.coordinator = coord
    sensor._device = _device()
    return sensor


# ── Current Plan ──────────────────────────────────────────────────────────────


class TestYarboCurrentPlanSensor:
    _plans = [
        {"id": 1, "name": "House Front", "areaIds": [100, 200]},
        {"id": 2, "name": "South Front", "areaIds": [135, 129]},
    ]

    def test_matches_plan_by_area_ids(self):
        s = _make(
            YarboCurrentPlanSensor,
            plan_feedback={"areaIds": [135, 129]},
            plan_data=self._plans,
        )
        assert s.native_value == "South Front"

    def test_order_independent_match(self):
        # areaIds order should not matter
        s = _make(
            YarboCurrentPlanSensor,
            plan_feedback={"areaIds": [129, 135]},
            plan_data=self._plans,
        )
        assert s.native_value == "South Front"

    def test_no_match_returns_none(self):
        s = _make(
            YarboCurrentPlanSensor,
            plan_feedback={"areaIds": [999]},
            plan_data=self._plans,
        )
        assert s.native_value is None

    def test_empty_feedback_returns_none(self):
        s = _make(YarboCurrentPlanSensor, plan_data=self._plans)
        assert s.native_value is None

    def test_empty_plan_list_returns_none(self):
        s = _make(YarboCurrentPlanSensor, plan_feedback={"areaIds": [135, 129]})
        assert s.native_value is None


# ── Clean Area ────────────────────────────────────────────────────────────────


class TestYarboCleanAreaSensor:
    def test_rounds_to_two_decimals(self):
        s = _make(YarboCleanAreaSensor, {"actualCleanArea": 620.61725})
        assert s.native_value == pytest.approx(620.62, abs=1e-2)

    def test_missing_returns_none(self):
        assert _make(YarboCleanAreaSensor).native_value is None


# ── Battery Consumption ───────────────────────────────────────────────────────


class TestYarboBatteryConsumptionSensor:
    def test_value(self):
        s = _make(YarboBatteryConsumptionSensor, {"battery_consumption": 32})
        assert s.native_value == 32.0

    def test_missing_returns_none(self):
        assert _make(YarboBatteryConsumptionSensor).native_value is None


# ── Plan Progress ─────────────────────────────────────────────────────────────


class TestYarboPlanProgressSensor:
    def test_half_done(self):
        s = _make(
            YarboPlanProgressSensor,
            {"actualCleanArea": 500.0, "totalCleanArea": 1000.0},
        )
        assert s.native_value == pytest.approx(50.0, abs=0.1)

    def test_clamped_at_100(self):
        # Guard against floating point slightly over 100
        s = _make(
            YarboPlanProgressSensor,
            {"actualCleanArea": 1010.0, "totalCleanArea": 1000.0},
        )
        assert s.native_value == 100.0

    def test_zero_total_returns_none(self):
        s = _make(
            YarboPlanProgressSensor, {"actualCleanArea": 500.0, "totalCleanArea": 0}
        )
        assert s.native_value is None

    def test_missing_actual_returns_none(self):
        s = _make(YarboPlanProgressSensor, {"totalCleanArea": 1000.0})
        assert s.native_value is None


# ── Remaining Area ────────────────────────────────────────────────────────────


class TestYarboRemainingAreaSensor:
    def test_remaining(self):
        s = _make(
            YarboRemainingAreaSensor,
            {"actualCleanArea": 400.0, "totalCleanArea": 1000.0},
        )
        assert s.native_value == pytest.approx(600.0, abs=0.01)

    def test_floored_at_zero(self):
        # Protect against actual > total due to rounding
        s = _make(
            YarboRemainingAreaSensor,
            {"actualCleanArea": 1010.0, "totalCleanArea": 1000.0},
        )
        assert s.native_value == 0.0

    def test_missing_returns_none(self):
        assert _make(YarboRemainingAreaSensor).native_value is None


# ── Time Remaining ────────────────────────────────────────────────────────────


class TestYarboTimeRemainingSensor:
    def test_value(self):
        s = _make(YarboTimeRemainingSensor, {"leftTime": 9141.32})
        assert s.native_value == pytest.approx(9141.0, abs=1.0)

    def test_floored_at_zero(self):
        s = _make(YarboTimeRemainingSensor, {"leftTime": -5.0})
        assert s.native_value == 0.0

    def test_missing_returns_none(self):
        assert _make(YarboTimeRemainingSensor).native_value is None


# ── Elapsed Time ──────────────────────────────────────────────────────────────


class TestYarboElapsedTimeSensor:
    def test_value(self):
        s = _make(YarboElapsedTimeSensor, {"duration": 8315})
        assert s.native_value == 8315.0

    def test_missing_returns_none(self):
        assert _make(YarboElapsedTimeSensor).native_value is None


# ── Total Plan Area ───────────────────────────────────────────────────────────


class TestYarboTotalPlanAreaSensor:
    def test_value(self):
        s = _make(YarboTotalPlanAreaSensor, {"totalCleanArea": 1269.243})
        assert s.native_value == pytest.approx(1269.24, abs=0.01)

    def test_missing_returns_none(self):
        assert _make(YarboTotalPlanAreaSensor).native_value is None


# ── Total Plan Time ───────────────────────────────────────────────────────────


class TestYarboTotalPlanTimeSensor:
    def test_value(self):
        s = _make(YarboTotalPlanTimeSensor, {"totalTime": 17888.0})
        assert s.native_value == 17888.0

    def test_missing_returns_none(self):
        assert _make(YarboTotalPlanTimeSensor).native_value is None
