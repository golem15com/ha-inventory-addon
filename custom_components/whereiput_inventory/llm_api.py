"""Agent-agnostic LLM API + search tool for the whereiput.it integration.

This exposes a single ``search_inventory`` tool to any LLM conversation agent
(via :func:`homeassistant.helpers.llm.async_register_api`). The HARD constraint
(D-01 / threat T-17-11): only the tool *spec* (name, description, parameters)
enters the agent's context. Inventory rows are fetched inside ``async_call`` and
returned to the agent as the per-call result only — never persisted, never
logged. Items are never registered as HA entities.

Client errors are mapped to :class:`homeassistant.exceptions.HomeAssistantError`
so the agent gets a clean failure instead of a stack trace (T-17-15).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .api import InventoryClient
from .const import CONF_AREAS, DOMAIN
from .exceptions import CannotConnect, InvalidAuth

_TOOL_PER_PAGE = 5

_TOOL_DESCRIPTION = (
    "Find where a household item is physically stored (its location and area). "
    "Call this whenever the user asks where something is, where they keep it, "
    "where they put it, or asks you to find an item."
)


def _map_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the server rows into minimal, None-safe match dicts.

    Only the four minimal fields cross to the caller — never the raw row.
    """
    return [
        {
            "name": row.get("name"),
            "location": (row.get("location") or {}).get("name"),
            "area": (row.get("area") or {}).get("name"),
            "quantity": row.get("quantity"),
        }
        for row in data.get("data", [])
    ]


class SearchInventoryTool(llm.Tool):
    """LLM tool that searches the inventory and returns rows per-call."""

    name = "search_inventory"
    description = _TOOL_DESCRIPTION
    parameters = vol.Schema({vol.Required("q"): str})

    def __init__(
        self, client: InventoryClient, areas: list[int] | None = None
    ) -> None:
        """Bind the per-entry client and (optional) narrowing area filter."""
        self._client = client
        self._areas = areas or None

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Fetch matches for the query; rows are returned, never persisted."""
        query = tool_input.tool_args["q"]
        try:
            data = await self._client.search(
                query, per_page=_TOOL_PER_PAGE, areas=self._areas
            )
        except (CannotConnect, InvalidAuth) as err:
            raise HomeAssistantError("Inventory search failed") from err
        return {"results": _map_rows(data)}


class WhereIPutAPI(llm.API):
    """An llm.API exposing the inventory search tool to any agent."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_id: str,
        name: str,
        areas: list[int] | None = None,
    ) -> None:
        """Store the per-entry id/name and the area filter."""
        super().__init__(hass=hass, id=api_id, name=name)
        self._areas = areas or None

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance exposing the search tool."""
        client = self._resolve_client()
        return llm.APIInstance(
            api=self,
            api_prompt=(
                "Use the search_inventory tool to look up where a household "
                "item is stored. Never assume a location — always call the tool."
            ),
            llm_context=llm_context,
            tools=[SearchInventoryTool(client, self._areas)],
        )

    def _resolve_client(self) -> InventoryClient:
        """Resolve the per-entry client from hass.data (id == whereiput-<entry_id>)."""
        entry_id = self.id.removeprefix("whereiput-")
        entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
        if not entry_data:
            raise HomeAssistantError("Inventory integration is not loaded")
        return entry_data["client"]


def build_api(hass: HomeAssistant, entry) -> WhereIPutAPI:
    """Build the per-entry llm.API, threading the narrowing area filter."""
    return WhereIPutAPI(
        hass,
        f"whereiput-{entry.entry_id}",
        entry.title,
        areas=entry.options.get(CONF_AREAS) or None,
    )
