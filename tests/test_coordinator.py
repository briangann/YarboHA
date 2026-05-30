"""Tests for coordinator.py pure functions."""

from custom_components.yarbo_bg.coordinator import _deep_merge


class TestDeepMerge:
    def test_adds_new_keys(self):
        target: dict = {}
        _deep_merge(target, {"a": 1})
        assert target == {"a": 1}

    def test_overwrites_scalar(self):
        target = {"a": 1}
        _deep_merge(target, {"a": 2})
        assert target["a"] == 2

    def test_merges_nested_dict(self):
        target = {"state": {"battery": 80, "speed": 3}}
        _deep_merge(target, {"state": {"battery": 75}})
        assert target["state"]["battery"] == 75
        assert target["state"]["speed"] == 3

    def test_replaces_non_dict_with_dict(self):
        target = {"state": "old"}
        _deep_merge(target, {"state": {"battery": 50}})
        assert target["state"] == {"battery": 50}

    def test_replaces_dict_with_scalar(self):
        target = {"state": {"battery": 80}}
        _deep_merge(target, {"state": "flat"})
        assert target["state"] == "flat"

    def test_preserves_online_key(self):
        target = {"__online__": True, "battery": 90}
        _deep_merge(target, {"__online__": False, "battery": 80})
        assert target["__online__"] is True
        assert target["battery"] == 80

    def test_preserves_heartbeat_key(self):
        target = {"HeartBeatMSG": {"ts": 100}}
        _deep_merge(target, {"HeartBeatMSG": {"ts": 200}})
        assert target["HeartBeatMSG"] == {"ts": 100}

    def test_online_not_added_from_source(self):
        target: dict = {}
        _deep_merge(target, {"__online__": True})
        assert "__online__" not in target

    def test_heartbeat_not_added_from_source(self):
        target: dict = {}
        _deep_merge(target, {"HeartBeatMSG": {"ts": 1}})
        assert "HeartBeatMSG" not in target

    def test_empty_source_unchanged(self):
        target = {"a": 1}
        _deep_merge(target, {})
        assert target == {"a": 1}

    def test_empty_target_and_source(self):
        target: dict = {}
        _deep_merge(target, {})
        assert target == {}
