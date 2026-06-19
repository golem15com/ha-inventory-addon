"""The whereiput_inventory.search service (D-02, HACS-04).

The deterministic, CI-verified search surface. Registered once (idempotent
across multiple entries) with ``SupportsResponse.OPTIONAL`` so it can be called
with ``return_response=True`` from scripts/automations and answer with a
structured ``{"matches": [{name, location, area, quantity}, ...]}`` dict, while
still being callable fire-and-forget. It resolves the calling entry's client
from ``hass.data`` and passes the per-entry area filter (CONF_AREAS) to
``client.search`` so the surface NARROWS scope only (T-17-13).

Rows are returned to the caller only — never logged or persisted (T-17-11).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import InventoryClient
from .const import CONF_AREAS, DEFAULT_PER_PAGE, DOMAIN
from .exceptions import CannotConnect, InvalidAuth
from .llm_api import _map_rows

SERVICE_SEARCH = "search"

_SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required("q"): cv.string,
        vol.Optional("per_page", default=DEFAULT_PER_PAGE): cv.positive_int,
    }
)


def _latest_entry_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return the most-recently set-up entry's stored data.

    With a single entry that is its client; with multiple entries the
    most-recently-set-up entry's client is used (documented in services.yaml).
    """
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("Inventory integration is not loaded")
    # dicts preserve insertion order; the last inserted entry is the latest set up.
    return next(reversed(entries.values()))


async def _handle_search(call: ServiceCall) -> ServiceResponse:
    """Search the inventory and return structured matches."""
    entry_data = _latest_entry_data(call.hass)
    client: InventoryClient = entry_data["client"]
    areas = entry_data.get("areas") or None

    try:
        data = await client.search(
            call.data["q"], per_page=call.data["per_page"], areas=areas
        )
    except (CannotConnect, InvalidAuth) as err:
        raise HomeAssistantError("Inventory search failed") from err

    return {"matches": _map_rows(data)}


def async_register_search_service(hass: HomeAssistant) -> None:
    """Register the search service once (idempotent across entries)."""
    if hass.services.has_service(DOMAIN, SERVICE_SEARCH):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        _handle_search,
        schema=_SEARCH_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def async_unregister_search_service(hass: HomeAssistant) -> None:
    """Remove the search service when the last entry is gone."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SEARCH)
