# Wave 0 RED — GREEN in Plan 03
"""RED stub: config flow (validate-on-connect).

Imports the not-yet-built config_flow module so it fails on the real missing
symbol (ModuleNotFoundError), not on a collection error. Plan 03 turns this
GREEN by adding custom_components/whereiput_inventory/config_flow.py.
"""

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory import config_flow  # noqa: F401
from custom_components.whereiput_inventory.const import DOMAIN

from .conftest import SEARCH_URL, mock_search_response


async def test_user_flow_success_creates_entry(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A valid token + a 200 search creates the config entry."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"base_url": "https://api.whereiput.it", "token": "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_aiohttp) -> None:
    """A 401 surfaces errors['base'] == 'invalid_auth'."""
    mock_aiohttp.get(SEARCH_URL, status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"base_url": "https://api.whereiput.it", "token": "inv_bad"},
    )
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_aiohttp) -> None:
    """A connection error surfaces errors['base'] == 'cannot_connect'."""
    from aiohttp import ClientError

    mock_aiohttp.get(SEARCH_URL, exception=ClientError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"base_url": "https://api.whereiput.it", "token": "inv_x"},
    )
    assert result["errors"]["base"] == "cannot_connect"
