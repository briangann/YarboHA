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


# ---------------------------------------------------------------------------
# fetch_devices_failed branch (line 94-95)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_fetch_devices_failed(hass: HomeAssistant):
    from custom_components.yarbo.config_flow import CannotConnect

    with (
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
            new=AsyncMock(return_value=(TOKEN, REFRESH)),
        ),
        patch(
            "custom_components.yarbo.config_flow.YarboConfigFlow._async_fetch_devices",
            new=AsyncMock(side_effect=CannotConnect),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "fetch_devices_failed"


# ---------------------------------------------------------------------------
# _async_login SDK error mapping (lines 197-218)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_login_maps_authentication_error(hass: HomeAssistant):
    from yarbo_robot_sdk import AuthenticationError

    from custom_components.yarbo.config_flow import InvalidAuth, YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.login.side_effect = AuthenticationError("bad")
        with pytest.raises(InvalidAuth):
            await cf._async_login(EMAIL, PASSWORD)


@pytest.mark.asyncio
async def test_async_login_maps_sdk_error(hass: HomeAssistant):
    from yarbo_robot_sdk import YarboSDKError

    from custom_components.yarbo.config_flow import CannotConnect, YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.login.side_effect = YarboSDKError("network")
        with pytest.raises(CannotConnect):
            await cf._async_login(EMAIL, PASSWORD)


# ---------------------------------------------------------------------------
# _async_fetch_devices SDK error mapping (lines 228-245)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_fetch_devices_maps_sdk_error(hass: HomeAssistant):
    from yarbo_robot_sdk import YarboSDKError

    from custom_components.yarbo.config_flow import CannotConnect, YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.restore_session.side_effect = YarboSDKError("err")
        with pytest.raises(CannotConnect):
            await cf._async_fetch_devices(EMAIL, TOKEN, REFRESH)


# ---------------------------------------------------------------------------
# YarboOptionsFlow (lines 255-310)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_flow_no_coordinator_shows_fetch_failed(hass: HomeAssistant):
    """Options flow when no coordinator in hass.data → fetch_devices_failed."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "fetch_devices_failed"


@pytest.mark.asyncio
async def test_options_flow_creates_entry(hass: HomeAssistant):
    """Options flow happy path: coordinator with client → device list → save."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.yarbo.const import CONF_KEEP_AWAKE_MODE, KEEP_AWAKE_ALWAYS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)

    device = MagicMock()
    device.sn = "SN001"
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord._client = MagicMock()
    coord._client.get_devices.return_value = [device]
    hass.data[DOMAIN] = {entry.entry_id: coord}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELECTED_DEVICES: ["SN001"],
            CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_ALWAYS,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SELECTED_DEVICES] == ["SN001"]


# ---------------------------------------------------------------------------
# _async_login success path + empty token (lines 205-214)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_login_success_returns_tokens(hass: HomeAssistant):
    """Happy path: login succeeds, token and refresh_token returned."""
    from custom_components.yarbo.config_flow import YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.login.return_value = None
        MockClient.return_value.token = "my-token"
        MockClient.return_value.refresh_token = "my-refresh"
        token, refresh = await cf._async_login(EMAIL, PASSWORD)
    assert token == "my-token"
    assert refresh == "my-refresh"


@pytest.mark.asyncio
async def test_async_login_empty_token_raises_invalid_auth(hass: HomeAssistant):
    """Login succeeds but client.token is empty → InvalidAuth."""
    from custom_components.yarbo.config_flow import InvalidAuth, YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.login.return_value = None
        MockClient.return_value.token = ""
        MockClient.return_value.refresh_token = ""
        with pytest.raises(InvalidAuth):
            await cf._async_login(EMAIL, PASSWORD)


@pytest.mark.asyncio
async def test_async_login_none_token_raises_invalid_auth(hass: HomeAssistant):
    """Login succeeds but client.token is None → InvalidAuth."""
    from custom_components.yarbo.config_flow import InvalidAuth, YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.login.return_value = None
        MockClient.return_value.token = None
        MockClient.return_value.refresh_token = "ref"
        with pytest.raises(InvalidAuth):
            await cf._async_login(EMAIL, PASSWORD)


# ---------------------------------------------------------------------------
# _async_fetch_devices success path (line 237)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_fetch_devices_success(hass: HomeAssistant):
    """Happy path: restore_session succeeds, get_devices returns list."""
    from custom_components.yarbo.config_flow import YarboConfigFlow as CF

    cf = CF.__new__(CF)
    cf.hass = hass
    device = MagicMock()
    device.sn = "SN001"
    with patch("yarbo_robot_sdk.YarboClient") as MockClient:
        MockClient.return_value.restore_session.return_value = None
        MockClient.return_value.get_devices.return_value = [device]
        MockClient.return_value.close.return_value = None
        devices = await cf._async_fetch_devices(EMAIL, TOKEN, REFRESH)
    assert len(devices) == 1
    assert devices[0].sn == "SN001"


# ---------------------------------------------------------------------------
# Reauth CannotConnect branch (lines 171-172)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reauth_cannot_connect(hass: HomeAssistant):
    """CannotConnect during reauth confirm → cannot_connect error."""
    from homeassistant.config_entries import SOURCE_REAUTH

    from custom_components.yarbo.config_flow import CannotConnect
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    with patch(
        "custom_components.yarbo.config_flow.YarboConfigFlow._async_login",
        new=AsyncMock(side_effect=CannotConnect),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "newpass"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Options flow edge cases (lines 260, 278-281, 287)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_flow_no_devices_selected_error(hass: HomeAssistant):
    """Options flow: submitting with empty selection → no_devices_selected."""
    from custom_components.yarbo.const import CONF_KEEP_AWAKE_MODE, KEEP_AWAKE_ALWAYS
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)

    device = MagicMock()
    device.sn = "SN001"
    device.name = "Yarbo Y1"
    device.model = "Y1"

    coord = MagicMock()
    coord._client = MagicMock()
    coord._client.get_devices.return_value = [device]
    hass.data[DOMAIN] = {entry.entry_id: coord}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SELECTED_DEVICES: [], CONF_KEEP_AWAKE_MODE: KEEP_AWAKE_ALWAYS},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices_selected"


@pytest.mark.asyncio
async def test_options_flow_get_devices_raises(hass: HomeAssistant):
    """Options flow: get_devices() raises → fetch_devices_failed error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={CONF_SELECTED_DEVICES: ["SN001"]},
    )
    entry.add_to_hass(hass)

    coord = MagicMock()
    coord._client = MagicMock()
    coord._client.get_devices.side_effect = Exception("timeout")
    hass.data[DOMAIN] = {entry.entry_id: coord}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "fetch_devices_failed"


@pytest.mark.asyncio
async def test_options_flow_empty_device_list(hass: HomeAssistant):
    """Options flow: get_devices() returns [] with no prior errors → no_devices_found."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD, DATA_ACCESS_TOKEN: TOKEN},
        options={CONF_SELECTED_DEVICES: []},
    )
    entry.add_to_hass(hass)

    coord = MagicMock()
    coord._client = MagicMock()
    coord._client.get_devices.return_value = []
    hass.data[DOMAIN] = {entry.entry_id: coord}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_devices_found"
