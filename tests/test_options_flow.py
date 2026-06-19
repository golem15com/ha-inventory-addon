# GREEN in Plan 03 (was Wave 0 RED in Plan 02)
"""Options flow tests (area filter, D-08).

The options flow reads the token's accessible areas from me/areas and stores an
optional area filter (default = none). It must NOT assign self.config_entry.
"""

from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory import config_flow
from custom_components.whereiput_inventory.const import CONF_AREAS, DOMAIN

from .conftest import AREAS_URL, mock_areas_response


@pytest.fixture(autouse=True)
async def _bypass_entry_setup(hass):
    """Set up the `homeassistant` component (so the manifest `conversation`
    dependency's default agent finds `homeassistant.exposed_entities`) and patch
    `async_setup_entry` to True — the options flow is what we assert, not entry
    setup. Pure test-harness plumbing.
    """
    from homeassistant.setup import async_setup_component

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    with patch(
        "custom_components.whereiput_inventory.async_setup_entry",
        return_value=True,
    ):
        yield


def _entry(hass: HomeAssistant, options=None):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "https://api.whereiput.it", "token": "inv_valid"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_flow_lists_areas_and_stores_selection(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """The options flow reads me/areas and persists the chosen area ids."""
    entry = _entry(hass)
    mock_aiohttp.get(AREAS_URL, payload=mock_areas_response)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    # The schema's multi_select must offer both mocked areas (ids 7 and 9).
    schema = result["data_schema"].schema
    areas_validator = next(
        validator for key, validator in schema.items() if str(key) == CONF_AREAS
    )
    # cv.multi_select stores the {id: name} mapping on its `.options` attribute.
    assert areas_validator.options == {7: "Garaż", 9: "Piwnica"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AREAS: [7]}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_AREAS] == [7]


async def test_options_flow_default_is_no_filter(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """Submitting nothing stores an empty area filter (default = none)."""
    entry = _entry(hass)
    mock_aiohttp.get(AREAS_URL, payload=mock_areas_response)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AREAS: []}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_AREAS] == []


async def test_options_flow_areas_error_surfaces_form(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A me/areas failure surfaces a form error, not a crash."""
    from aiohttp import ClientError

    entry = _entry(hass)
    mock_aiohttp.get(AREAS_URL, exception=ClientError())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


def test_options_flow_does_not_assign_config_entry() -> None:
    """The OptionsFlow must not set self.config_entry (provided by HA)."""
    import inspect

    src = inspect.getsource(config_flow.WhereIPutOptionsFlow)
    assert "self.config_entry =" not in src
