"""Shared entity filtering helpers for Yarbo platforms."""

from __future__ import annotations

from yarbo_robot_sdk.device_helpers import extract_field


def control_matches_device(coordinator, device, ctrl_def) -> bool:
    """Return whether a configured control applies to the current device head."""
    compatible_head_types = getattr(ctrl_def, "compatible_head_types", None)
    if not compatible_head_types:
        return True

    if not coordinator.data:
        return False
    device_data = coordinator.data.get(device.sn)
    if device_data is None:
        return False

    head_type = extract_field(device_data, "HeadMsg.head_type")
    try:
        return int(head_type) in compatible_head_types
    except (TypeError, ValueError):
        return False
