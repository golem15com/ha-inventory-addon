"""Unit tests for InventoryClient (the one piece of real custom runtime code).

Stubs the two whereiput.it inventory API endpoints with aioresponses and asserts
URL/params/headers, response mapping, error mapping, trailing-slash
normalization, single + multi area filtering, and that the token is never
logged.
"""

import logging

import pytest
from aiohttp import ClientError

from custom_components.whereiput_inventory.api import InventoryClient
from custom_components.whereiput_inventory.const import DEFAULT_PER_PAGE
from custom_components.whereiput_inventory.exceptions import (
    CannotConnect,
    InvalidAuth,
)

from .conftest import (
    AREAS_URL,
    SEARCH_URL,
    TOKEN,
    mock_areas_response,
    mock_search_response,
)


@pytest.fixture
async def client(hass):
    """An InventoryClient over HA's shared aiohttp session."""
    from homeassistant.helpers import aiohttp_client

    session = aiohttp_client.async_get_clientsession(hass)
    return InventoryClient(session, "https://inventory.example.com", TOKEN)


# --- search() happy path --------------------------------------------------

async def test_search_hits_correct_url_with_bearer(client, mock_aiohttp) -> None:
    """search() GETs items/search with q + per_page + a Bearer header."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    result = await client.search("młotek")

    assert result["data"][0]["name"] == "młotek"
    assert result["data"][0]["location"]["name"] == "Szuflada"

    request = _only_request(mock_aiohttp)
    assert "api/v1/inventory/items/search" in str(request[1])
    headers = request[2]["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/json"


async def test_search_passes_query_via_params_not_concat(
    client, mock_aiohttp
) -> None:
    """The query rides in params= (auto-encoded), never string-concatenated."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    await client.search("a b&c")

    request = _only_request(mock_aiohttp)
    params = request[2]["params"]
    assert params["q"] == "a b&c"
    assert params["per_page"] == DEFAULT_PER_PAGE
    # The raw query must NOT be baked into the path.
    assert "a b&c" not in str(request[1])


async def test_search_single_area_adds_area_param(client, mock_aiohttp) -> None:
    """areas=[7] adds a single area=7 param (server reads one int)."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    await client.search("młotek", areas=[7])

    params = _only_request(mock_aiohttp)[2]["params"]
    assert params["area"] == 7


async def test_search_multi_area_fans_out_and_merges(client, mock_aiohttp) -> None:
    """areas=[7,9] issues one request per area and merges data (never widens)."""
    row7 = {"data": [{"name": "a", "location": None, "area": {"name": "A7"},
                      "quantity": 1}], "meta": {}}
    row9 = {"data": [{"name": "b", "location": None, "area": {"name": "A9"},
                      "quantity": 1}], "meta": {}}
    mock_aiohttp.get(SEARCH_URL, payload=row7)
    mock_aiohttp.get(SEARCH_URL, payload=row9)

    result = await client.search("x", areas=[7, 9])
    names = sorted(r["name"] for r in result["data"])
    assert names == ["a", "b"]


# --- search() error mapping ----------------------------------------------

async def test_search_401_raises_invalid_auth(client, mock_aiohttp) -> None:
    mock_aiohttp.get(SEARCH_URL, status=401)
    with pytest.raises(InvalidAuth):
        await client.search("młotek")


async def test_search_403_raises_invalid_auth(client, mock_aiohttp) -> None:
    mock_aiohttp.get(SEARCH_URL, status=403)
    with pytest.raises(InvalidAuth):
        await client.search("młotek")


async def test_search_500_raises_cannot_connect(client, mock_aiohttp) -> None:
    mock_aiohttp.get(SEARCH_URL, status=500)
    with pytest.raises(CannotConnect):
        await client.search("młotek")


async def test_search_network_error_raises_cannot_connect(
    client, mock_aiohttp
) -> None:
    mock_aiohttp.get(SEARCH_URL, exception=ClientError())
    with pytest.raises(CannotConnect):
        await client.search("młotek")


async def test_search_200_non_json_body_raises_cannot_connect(
    client, mock_aiohttp
) -> None:
    """A 200 with an HTML/non-JSON body (wrong host — SPA instead of API)
    must map to CannotConnect, not propagate a raw JSONDecodeError (WR-02)."""
    mock_aiohttp.get(
        SEARCH_URL,
        status=200,
        body="<!DOCTYPE html><html><body>SPA</body></html>",
        content_type="text/html",
    )
    with pytest.raises(CannotConnect):
        await client.search("młotek")


# --- areas() --------------------------------------------------------------

async def test_areas_returns_contract_shape(client, mock_aiohttp) -> None:
    """areas() GETs me/areas and returns {data:[{id,name,is_owner}]}."""
    mock_aiohttp.get(AREAS_URL, payload=mock_areas_response)
    result = await client.areas()

    assert result["data"][0]["id"] == 7
    assert result["data"][0]["is_owner"] is True
    request = _only_request(mock_aiohttp)
    assert "api/v1/inventory/me/areas" in str(request[1])
    assert request[2]["headers"]["Authorization"] == f"Bearer {TOKEN}"


async def test_areas_error_raises_cannot_connect(client, mock_aiohttp) -> None:
    mock_aiohttp.get(AREAS_URL, status=500)
    with pytest.raises(CannotConnect):
        await client.areas()


# --- normalization + security --------------------------------------------

async def test_base_url_trailing_slash_normalized(hass, mock_aiohttp) -> None:
    """A trailing slash in base_url is stripped (no double-slash in the path)."""
    from homeassistant.helpers import aiohttp_client

    session = aiohttp_client.async_get_clientsession(hass)
    client = InventoryClient(session, "https://inventory.example.com/", TOKEN)
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    await client.search("młotek")

    url = str(_only_request(mock_aiohttp)[1])
    assert "//api/v1" not in url
    assert "api/v1/inventory/items/search" in url


async def test_token_never_logged(client, mock_aiohttp, caplog) -> None:
    """The token must never appear in any logged string."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    with caplog.at_level(logging.DEBUG):
        await client.search("młotek")
    assert TOKEN not in caplog.text


# --- helpers --------------------------------------------------------------

def _only_request(mock_aiohttp):
    """Return the (method, url, kwargs) tuple of the first recorded request."""
    for key, calls in mock_aiohttp.requests.items():
        method, url = key
        kwargs = calls[0].kwargs
        return (method, url, kwargs)
    raise AssertionError("no request was recorded")
