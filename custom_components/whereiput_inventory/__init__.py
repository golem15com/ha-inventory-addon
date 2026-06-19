"""The whereiput.it Inventory integration.

Plan 03 ships the entry-point skeleton: ``async_setup_entry`` builds an
``InventoryClient`` from the config entry and stores it per ``entry_id`` under
``hass.data[DOMAIN]``; ``async_unload_entry`` removes it. Plan 04 wires the
service, LLM tool and conversation entity onto the per-entry client at the
``# surfaces registered in Plan 04`` anchor below.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InventoryClient
from .const import CONF_AREAS, CONF_BASE_URL, CONF_TOKEN, DOMAIN
from .llm_api import build_api
from .services import (
    async_register_search_service,
    async_unregister_search_service,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Build the per-entry InventoryClient and stash it under hass.data."""
    client = InventoryClient(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_TOKEN],
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        # The per-entry area filter NARROWS scope only (D-08); [] = no filter.
        "areas": entry.options.get(CONF_AREAS) or None,
    }

    # Reload the entry when its options (e.g. the area filter) change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # surfaces registered in Plan 04 (service, LLM tool, conversation entity)
    # 1. The search service (idempotent across entries; removed on last unload).
    async_register_search_service(hass)
    # 2. The agent-agnostic LLM API; unregistered with the entry.
    unreg = llm.async_register_api(hass, build_api(hass, entry))
    entry.async_on_unload(unreg)
    # 3. The offline EN+PL ConversationEntity is wired in Task 2.

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Drop the per-entry client + surfaces on unload."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    # Remove the shared service only once the last entry is gone.
    async_unregister_search_service(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change so the new filter takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
