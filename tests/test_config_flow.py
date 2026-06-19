# GREEN in Plan 03 (was Wave 0 RED in Plan 02)
"""Config flow tests (validate-on-connect, https-only, multi-entry).

Asserts every <behavior> bullet of Plan 03 Task 1:
- the user form is shown with no input,
- a non-https base_url is rejected as invalid_url BEFORE any network call,
- a valid https URL + a 200 search creates the entry,
- a 401 maps to invalid_auth, a ClientError maps to cannot_connect,
- two distinct base_url+token pairs both create entries (D-06),
- an identical pair aborts as already_configured (unique_id de-dupe, token hashed).
"""

from aiohttp import ClientError

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory import config_flow  # noqa: F401
from custom_components.whereiput_inventory.const import CONF_BASE_URL, CONF_TOKEN, DOMAIN

from .conftest import SEARCH_URL, mock_search_response


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """async_step_user with no input shows the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    # base_url + token both present in the schema.
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_BASE_URL in schema_keys
    assert CONF_TOKEN in schema_keys


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
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_BASE_URL: "https://api.whereiput.it",
        CONF_TOKEN: "inv_valid",
    }


async def test_user_flow_rejects_non_https_before_network(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A non-https base_url is rejected as invalid_url BEFORE any network call."""
    # No mock registered: if the flow made a network call it would raise a
    # connection error (aioresponses with no match), proving no call happened.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "http://api.whereiput.it", CONF_TOKEN: "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_url"
    # aioresponses recorded zero requests.
    assert not mock_aiohttp.requests


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_aiohttp) -> None:
    """A 401 surfaces errors['base'] == 'invalid_auth' and creates no entry."""
    mock_aiohttp.get(SEARCH_URL, status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_bad"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_aiohttp) -> None:
    """A connection error surfaces errors['base'] == 'cannot_connect'."""
    mock_aiohttp.get(SEARCH_URL, exception=ClientError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_x"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_two_distinct_pairs_both_create_entries(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """D-06: two different base_url+token pairs both create config entries."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response, repeat=True)

    # First entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_one"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Second entry — a different token => a different unique_id => allowed.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_two"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_identical_pair_aborts_already_configured(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """The same base_url+token twice aborts as already_configured (de-dupe)."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response, repeat=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_dup"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_dup"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_unique_id_does_not_store_raw_token(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """T-17-08: the unique_id is a hash, never the raw token."""
    mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://api.whereiput.it", CONF_TOKEN: "inv_secret_token"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id is not None
    assert "inv_secret_token" not in entry.unique_id
