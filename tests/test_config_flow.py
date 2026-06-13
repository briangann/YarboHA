"""Tests for YarboConfigFlow and YarboOptionsFlow.

Uses the real hass fixture (pytest-homeassistant-custom-component) so HA
discovers and loads the integration from ./custom_components/.
SDK network calls are patched so no real credentials or MQTT are needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.yarbo.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    DATA_ACCESS_TOKEN,
    DOMAIN,
)

EMAIL = "test@example.com"
PASSWORD = "secret"
TOKEN = "access-token"
REFRESH = "refresh-token"


def _fake_device(sn="SN001", name="Yarbo Y1", model="Y1"):
    d = MagicMock()
    d.sn = sn
    d.name = name
    d.model = model
    return d


def _patch_login(token=TOKEN, refresh=REFRESH):
    return patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new_callable=lambda: lambda self: AsyncMock(return_value=(token, refresh)),
    )


# ---------------------------------------------------------------------------
# async_step_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_shows_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_invalid_auth(hass: HomeAssistant):
    from custom_components.yarbo.config_flow import InvalidAuth

    with patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new=AsyncMock(side_effect=InvalidAuth),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_user_step_cannot_connect(hass: HomeAssistant):
    from custom_components.yarbo.config_flow import CannotConnect

    with patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new=AsyncMock(side_effect=CannotConnect),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_no_devices_found(hass: HomeAssistant):
    with (
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
            new=AsyncMock(return_value=(TOKEN, REFRESH)),
        ),
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_fetch_devices",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices_found"


@pytest.mark.asyncio
async def test_full_flow_creates_entry(hass: HomeAssistant):
    with (
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
            new=AsyncMock(return_value=(TOKEN, REFRESH)),
        ),
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_fetch_devices",
            new=AsyncMock(return_value=[_fake_device("SN001")]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_devices"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"][CONF_EMAIL] == EMAIL
    assert result["data"][DATA_ACCESS_TOKEN] == TOKEN
    assert result["options"][CONF_SELECTED_DEVICES] == ["SN001"]


@pytest.mark.asyncio
async def test_select_devices_no_selection_shows_error(hass: HomeAssistant):
    with (
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
            new=AsyncMock(return_value=(TOKEN, REFRESH)),
        ),
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_fetch_devices",
            new=AsyncMock(return_value=[_fake_device("SN001")]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_DEVICES: []},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices_selected"
