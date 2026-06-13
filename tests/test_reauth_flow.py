"""Tests for YarboConfigFlow reauth flow (lines 152-186)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yarbo.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DATA_ACCESS_TOKEN,
    DATA_REFRESH_TOKEN,
    DOMAIN,
)

EMAIL = "user@example.com"
TOKEN = "tok"
REFRESH = "ref"


def _make_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: "old",
            DATA_ACCESS_TOKEN: TOKEN,
            DATA_REFRESH_TOKEN: REFRESH,
        },
        options={},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_reauth_shows_confirm_form(hass: HomeAssistant):
    entry = _make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


@pytest.mark.asyncio
async def test_reauth_invalid_password(hass: HomeAssistant):
    from custom_components.yarbo.config_flow import InvalidAuth

    entry = _make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    with patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new=AsyncMock(side_effect=InvalidAuth),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "wrong"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_reauth_success_aborts_flow(hass: HomeAssistant):
    entry = _make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    with patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new=AsyncMock(return_value=("new-tok", "new-ref")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new-pass"},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Entry data updated with new tokens
    assert entry.data[DATA_ACCESS_TOKEN] == "new-tok"
    assert entry.data[DATA_REFRESH_TOKEN] == "new-ref"
    assert entry.data[CONF_PASSWORD] == "new-pass"
