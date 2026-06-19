# GREEN in Plan 03 (was Wave 0 RED in Plan 02); URL policy updated in Plan 05.
"""Config flow tests (validate-on-connect, self-host-first URL policy, multi-entry).

Asserts every <behavior> bullet of Plan 03 Task 1 + the Plan-05 URL policy:
- the user form is shown with no input,
- a base_url with a non-http(s) scheme is rejected as invalid_url BEFORE any network call,
- http:// to a PUBLIC host is rejected as insecure_url BEFORE any network call,
- http:// to a LOCAL/PRIVATE host (localhost, *.local, RFC1918 IP) is ACCEPTED,
- a valid https URL + a 200 search creates the entry,
- a 401 maps to invalid_auth, a ClientError maps to cannot_connect,
- two distinct base_url+token pairs both create entries (D-06),
- an identical pair aborts as already_configured (unique_id de-dupe, token hashed).
"""

import re
from unittest.mock import patch

import pytest

from aiohttp import ClientError

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.whereiput_inventory import config_flow  # noqa: F401
from custom_components.whereiput_inventory.const import CONF_BASE_URL, CONF_TOKEN, DOMAIN

from .conftest import SEARCH_URL, mock_search_response


@pytest.fixture(autouse=True)
async def _bypass_entry_setup(hass):
    """Test the flow in isolation — don't run the real entry setup.

    ``async_setup_entry`` is patched to True (the canonical HA config-flow
    pattern: the flow's own logic — validate-on-connect, errors, unique_id — is
    what we assert, not entry setup). The ``homeassistant`` component is set up
    first so that when creating an entry resolves the manifest ``conversation``
    dependency, its default agent finds ``homeassistant.exposed_entities`` and
    starts without a KeyError. Pure test-harness plumbing.
    """
    from homeassistant.setup import async_setup_component

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    with patch(
        "custom_components.whereiput_inventory.async_setup_entry",
        return_value=True,
    ):
        yield


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
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_BASE_URL: "https://inventory.example.com",
        CONF_TOKEN: "inv_valid",
    }


async def test_user_flow_rejects_non_http_scheme_before_network(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """A non-http(s) scheme is rejected as invalid_url BEFORE any network call."""
    # No mock registered: if the flow made a network call it would raise a
    # connection error (aioresponses with no match), proving no call happened.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "ftp://inventory.example.com", CONF_TOKEN: "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_url"
    # aioresponses recorded zero requests.
    assert not mock_aiohttp.requests


async def test_user_flow_rejects_http_public_host_before_network(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """http:// to a PUBLIC host is rejected as insecure_url BEFORE any call (T-17-07)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "http://example.com", CONF_TOKEN: "inv_valid"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "insecure_url"
    # No plaintext bearer token left the host.
    assert not mock_aiohttp.requests


async def test_user_flow_accepts_http_localhost(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """http://localhost (self-host default) is accepted and creates an entry."""
    mock_aiohttp.get(
        re.compile(
            r"http://localhost:8088/api/v1/inventory/items/search(\?.*)?$"
        ),
        payload=mock_search_response,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "http://localhost:8088", CONF_TOKEN: "inv_local"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BASE_URL] == "http://localhost:8088"


async def test_user_flow_accepts_http_private_ip(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """http:// to an RFC1918 private IP (192.168.x.x) is accepted."""
    mock_aiohttp.get(
        re.compile(
            r"http://192\.168\.1\.50:8088/api/v1/inventory/items/search(\?.*)?$"
        ),
        payload=mock_search_response,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "http://192.168.1.50:8088", CONF_TOKEN: "inv_lan"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BASE_URL] == "http://192.168.1.50:8088"


async def test_user_flow_accepts_http_mdns_local(
    hass: HomeAssistant, mock_aiohttp
) -> None:
    """http:// to a *.local mDNS hostname is accepted."""
    mock_aiohttp.get(
        re.compile(
            r"http://inventory\.local:8088/api/v1/inventory/items/search(\?.*)?$"
        ),
        payload=mock_search_response,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "http://inventory.local:8088", CONF_TOKEN: "inv_mdns"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BASE_URL] == "http://inventory.local:8088"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_aiohttp) -> None:
    """A 401 surfaces errors['base'] == 'invalid_auth' and creates no entry."""
    mock_aiohttp.get(SEARCH_URL, status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_bad"},
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
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_x"},
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
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_one"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Second entry — a different token => a different unique_id => allowed.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_two"},
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
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_dup"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_dup"},
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
        {CONF_BASE_URL: "https://inventory.example.com", CONF_TOKEN: "inv_secret_token"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id is not None
    assert "inv_secret_token" not in entry.unique_id
