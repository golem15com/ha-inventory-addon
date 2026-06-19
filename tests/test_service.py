"""Tests for the whereiput_inventory.search service (Plan 04).

The service is the deterministic, CI-verified search surface (RESEARCH Open Q4):
it is registered in async_setup_entry with supports_response, returns a
structured {"matches": [{name,location,area,quantity}, ...]} dict, maps
location/area from the nested row objects (None-safe), and passes the per-entry
area filter (entry.options[CONF_AREAS]) to client.search(areas=...).
"""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant, SupportsResponse

from custom_components.whereiput_inventory.const import CONF_AREAS, DOMAIN

from .conftest import SEARCH_URL, mock_search_response


async def _setup_entry(hass: HomeAssistant, options=None):
    """Set up a config entry and return it."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.whereiput.it", "token": "inv_valid"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_search_service_returns_structured_matches(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """Calling whereiput_inventory.search returns the {matches:[...]} shape."""
    await _setup_entry(hass)

    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)

    response = await hass.services.async_call(
        DOMAIN,
        "search",
        {"q": "młotek"},
        blocking=True,
        return_response=True,
    )
    assert "matches" in response
    first = response["matches"][0]
    assert {"name", "location", "area", "quantity"} <= set(first.keys())


async def test_search_service_maps_nested_location_and_area(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """location/area are flattened from the nested row objects."""
    await _setup_entry(hass)
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)

    response = await hass.services.async_call(
        DOMAIN,
        "search",
        {"q": "młotek"},
        blocking=True,
        return_response=True,
    )
    first = response["matches"][0]
    assert first["name"] == "młotek"
    assert first["location"] == "Szuflada"
    assert first["area"] == "Garaż"
    assert first["quantity"] == 2


async def test_search_service_none_safe_location_area(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A row with missing/null location+area maps to None, not a KeyError."""
    await _setup_entry(hass)
    mock_aiohttp.get(
        SEARCH_URL,
        payload={
            "data": [{"name": "kabel", "location": None, "quantity": 1}],
            "meta": {},
        },
    )

    response = await hass.services.async_call(
        DOMAIN,
        "search",
        {"q": "kabel"},
        blocking=True,
        return_response=True,
    )
    first = response["matches"][0]
    assert first["location"] is None
    assert first["area"] is None


async def test_search_service_passes_entry_area_filter(
    hass: HomeAssistant,
) -> None:
    """The per-entry CONF_AREAS option is passed to client.search(areas=...)."""
    entry = await _setup_entry(hass, options={CONF_AREAS: [7, 9]})
    client = hass.data[DOMAIN][entry.entry_id]["client"]

    with patch.object(
        client, "search", return_value={"data": [], "meta": {}}
    ) as mock_search:
        await hass.services.async_call(
            DOMAIN,
            "search",
            {"q": "młotek"},
            blocking=True,
            return_response=True,
        )

    assert mock_search.await_count == 1
    assert mock_search.await_args.kwargs.get("areas") == [7, 9]


async def test_search_service_supports_response(
    hass: HomeAssistant,
) -> None:
    """The service is registered with a response (SupportsResponse != NONE)."""
    await _setup_entry(hass)
    assert hass.services.has_service(DOMAIN, "search")
    service = hass.services.async_services_for_domain(DOMAIN)["search"]
    assert service.supports_response is not SupportsResponse.NONE


async def test_search_service_removed_on_unload(
    hass: HomeAssistant,
) -> None:
    """Unloading the last entry removes the service."""
    entry = await _setup_entry(hass)
    assert hass.services.has_service(DOMAIN, "search")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "search")
