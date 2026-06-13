"""Tests for websocket_api._handle_map_zones.

Uses the hass fixture from pytest-homeassistant-custom-component so we get
a real HomeAssistant event loop and a real WebSocket connection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.yarbo.const import DOMAIN
from custom_components.yarbo.websocket_api import WS_TYPE_MAP_ZONES, async_register

GEOJSON = {"type": "FeatureCollection", "features": []}
SN = "SN001"


def _stub_coordinator(sn: str, geojson=None, gps_ref=None):
    coord = MagicMock()
    coord.map_data = {sn: geojson} if geojson is not None else {}
    coord.gps_refs = {sn: {"ref": gps_ref}} if gps_ref is not None else {}
    return coord


@pytest.fixture
def hass_with_yarbo(hass: HomeAssistant):
    """Register the WebSocket command and seed hass.data with a coordinator."""
    async_register(hass)
    coord = _stub_coordinator(
        SN,
        geojson=GEOJSON,
        gps_ref={"latitude": 37.1, "longitude": -122.0},
    )
    hass.data[DOMAIN] = {"entry_1": coord}
    return hass


@pytest.mark.asyncio
async def test_map_zones_returns_geojson(hass_with_yarbo, hass_ws_client):
    """Happy path: sn exists and has map data."""
    client = await hass_ws_client(hass_with_yarbo)
    await client.send_json({"id": 1, "type": WS_TYPE_MAP_ZONES, "sn": SN})
    msg = await client.receive_json()

    assert msg["success"] is True
    result = msg["result"]
    assert result["sn"] == SN
    assert result["geojson"] == GEOJSON
    assert result["center"]["latitude"] == pytest.approx(37.1)
    assert result["center"]["longitude"] == pytest.approx(-122.0)


@pytest.mark.asyncio
async def test_map_zones_no_center_when_no_gps_ref(hass: HomeAssistant, hass_ws_client):
    """Map exists but no GPS reference → center is None."""
    async_register(hass)
    coord = _stub_coordinator(SN, geojson=GEOJSON)  # no gps_ref
    hass.data[DOMAIN] = {"entry_1": coord}

    client = await hass_ws_client(hass)
    await client.send_json({"id": 2, "type": WS_TYPE_MAP_ZONES, "sn": SN})
    msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"]["center"] is None


@pytest.mark.asyncio
async def test_map_zones_unknown_sn_returns_error(hass: HomeAssistant, hass_ws_client):
    """Unknown SN → error response."""
    async_register(hass)
    coord = _stub_coordinator(SN, geojson=GEOJSON)
    hass.data[DOMAIN] = {"entry_1": coord}

    client = await hass_ws_client(hass)
    await client.send_json({"id": 3, "type": WS_TYPE_MAP_ZONES, "sn": "UNKNOWN"})
    msg = await client.receive_json()

    assert msg["success"] is False
    assert "UNKNOWN" in msg["error"]["message"]


@pytest.mark.asyncio
async def test_map_zones_no_domain_data(hass: HomeAssistant, hass_ws_client):
    """No DOMAIN data at all → error response."""
    async_register(hass)
    hass.data.pop(DOMAIN, None)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 4, "type": WS_TYPE_MAP_ZONES, "sn": SN})
    msg = await client.receive_json()

    assert msg["success"] is False


@pytest.mark.asyncio
async def test_async_register_idempotent(hass: HomeAssistant):
    """Calling async_register twice doesn't register the command twice."""
    async_register(hass)
    async_register(hass)  # must not raise
    assert hass.data.get("yarbo_ws_registered") is True
