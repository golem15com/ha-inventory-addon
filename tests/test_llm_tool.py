# Wave 0 RED — GREEN in Plan 04
"""RED stub: agent-agnostic LLM search tool.

Imports the not-yet-built llm_api module, instantiates the search tool, calls
async_call with q="młotek" and asserts a dict {"results":[{name,location,area,
quantity}]} is returned. Also asserts a client error propagates as a
HomeAssistantError (not a bare Exception). Plan 04 turns this GREEN.
"""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.whereiput_inventory import llm_api  # noqa: F401

from .conftest import SEARCH_URL, mock_search_response


async def test_search_tool_returns_results(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """The tool maps rows into {"results":[{name,location,area,quantity}]}."""
    from homeassistant.helpers import aiohttp_client

    from custom_components.whereiput_inventory.api import InventoryClient

    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    client = InventoryClient(
        aiohttp_client.async_get_clientsession(hass),
        "https://api.whereiput.it",
        "inv_valid",
    )
    tool = llm_api.SearchInventoryTool(client)
    result = await tool.async_call(hass, _tool_input("młotek"), _llm_context())

    assert "results" in result
    first = result["results"][0]
    assert {"name", "location", "area", "quantity"} <= set(first.keys())


async def test_search_tool_client_error_raises_haerror(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A client failure propagates as HomeAssistantError, never a bare Exception."""
    from aiohttp import ClientError
    from homeassistant.helpers import aiohttp_client

    from custom_components.whereiput_inventory.api import InventoryClient

    mock_aiohttp.get(SEARCH_URL, exception=ClientError())
    client = InventoryClient(
        aiohttp_client.async_get_clientsession(hass),
        "https://api.whereiput.it",
        "inv_valid",
    )
    tool = llm_api.SearchInventoryTool(client)
    with pytest.raises(HomeAssistantError):
        await tool.async_call(hass, _tool_input("młotek"), _llm_context())


async def test_tool_name_and_minimal_fields(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """The tool advertises name=search_inventory and returns only minimal fields."""
    from homeassistant.helpers import aiohttp_client

    from custom_components.whereiput_inventory.api import InventoryClient

    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    client = InventoryClient(
        aiohttp_client.async_get_clientsession(hass),
        "https://api.whereiput.it",
        "inv_valid",
    )
    tool = llm_api.SearchInventoryTool(client)
    assert tool.name == "search_inventory"

    result = await tool.async_call(hass, _tool_input("młotek"), _llm_context())
    first = result["results"][0]
    # Only the four minimal fields cross to the agent — never the raw row.
    assert set(first.keys()) == {"name", "location", "area", "quantity"}


async def test_llm_api_registered_and_unregistered_with_entry(
    hass: HomeAssistant,
) -> None:
    """The llm.API is registered on setup and unregistered on unload."""
    from homeassistant.helpers import llm
    from homeassistant.setup import async_setup_component

    from custom_components.whereiput_inventory.const import DOMAIN
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.whereiput.it", "token": "inv_valid"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    api_id = f"whereiput-{entry.entry_id}"
    apis = llm.async_get_apis(hass)
    assert any(a.id == api_id for a in apis)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    apis = llm.async_get_apis(hass)
    assert not any(a.id == api_id for a in apis)


def _tool_input(q: str):
    from homeassistant.helpers import llm

    return llm.ToolInput(tool_name="search_inventory", tool_args={"q": q})


def _llm_context():
    from homeassistant.helpers import llm

    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant=None,
        device_id=None,
    )
