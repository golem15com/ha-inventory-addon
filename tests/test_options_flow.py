# Wave 0 RED — GREEN in Plan 03
"""RED stub: options flow (area filter).

Imports the not-yet-built config_flow module (which will host the OptionsFlow).
Asserts the options flow lists areas from a mocked me/areas and stores the
selected area ids. Plan 03 turns this GREEN.
"""

import pytest

from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory import config_flow  # noqa: F401
from custom_components.whereiput_inventory.const import CONF_AREAS, DOMAIN

from .conftest import AREAS_URL, mock_areas_response


async def test_options_flow_lists_areas_and_stores_selection(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """The options flow reads me/areas and persists the chosen area ids."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.whereiput.it", "token": "inv_valid"},
        options={},
    )
    entry.add_to_hass(hass)

    mock_aiohttp.get(AREAS_URL, payload=mock_areas_response)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AREAS: [7]}
    )
    assert entry.options[CONF_AREAS] == [7]
