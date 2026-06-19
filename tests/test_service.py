# Wave 0 RED — GREEN in Plan 04
"""RED stub: whereiput_inventory.search service.

Asserts the service returns structured response data
{"matches": [{"name","location","area","quantity"}, ...]}. Plan 04 registers
the service (supports_response) in async_setup_entry. RED until then: the
service is not registered, so the call raises ServiceNotFound.
"""

import pytest

from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory.const import DOMAIN

from .conftest import SEARCH_URL, mock_search_response


async def test_search_service_returns_structured_matches(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """Calling whereiput_inventory.search returns the {matches:[...]} shape."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.whereiput.it", "token": "inv_valid"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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
