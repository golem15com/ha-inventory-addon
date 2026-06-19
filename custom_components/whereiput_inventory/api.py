"""Async aiohttp client for the whereiput.it inventory API.

This is the integration's only real custom runtime code. Every surface (config
flow, options flow, service, LLM tool, conversation entity) calls through it.

Security invariants:
- The Authorization header / token is NEVER logged.
- The search query rides in ``params=`` (auto URL-encoded), never concatenated
  into the URL (tampering / injection mitigation).
- The client NEVER widens the server-side permission scope. Multi-area search
  fans out one request per area and merges the (already-scoped) rows.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import DEFAULT_PER_PAGE
from .exceptions import CannotConnect, InvalidAuth

_TIMEOUT = 10


class InventoryClient:
    """Thin async client over the inventory search + areas endpoints."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        """Store the injected HA session, normalized base URL and the token."""
        self._session = session
        self._base = base_url.rstrip("/")
        self._token = token

    @property
    def _headers(self) -> dict[str, str]:
        # Never logged — see _request.
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    async def search(
        self,
        q: str,
        per_page: int = DEFAULT_PER_PAGE,
        areas: list[int] | None = None,
    ) -> dict[str, Any]:
        """Search items by name.

        ``areas`` is intersect-only and never widens scope:
        - one id  -> a single ``?area=`` param
        - many ids -> one request per area, rows merged client-side
        """
        base_params: dict[str, Any] = {"q": q, "per_page": per_page}

        if not areas:
            return await self._get(
                f"{self._base}/api/v1/inventory/items/search", params=base_params
            )

        if len(areas) == 1:
            params = {**base_params, "area": areas[0]}
            return await self._get(
                f"{self._base}/api/v1/inventory/items/search", params=params
            )

        # Multi-area: the server reads a single int, so fan out and merge.
        # meta.total is aggregated across areas (last-wins would mis-report it).
        merged: list[Any] = []
        total = 0
        for area_id in areas:
            params = {**base_params, "area": area_id}
            result = await self._get(
                f"{self._base}/api/v1/inventory/items/search", params=params
            )
            merged.extend(result.get("data", []))
            total += result.get("meta", {}).get("total", 0)
        return {"data": merged, "meta": {"total": total}}

    async def areas(self) -> dict[str, Any]:
        """Return the token's accessible areas: {data:[{id,name,is_owner}]}."""
        return await self._get(f"{self._base}/api/v1/inventory/me/areas")

    async def _get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET ``url`` with the Bearer header, mapping failures to typed errors."""
        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._session.get(
                    url, params=params, headers=self._headers
                ) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth
                    if resp.status != 200:
                        raise CannotConnect(resp.status)
                    # A 200 with a non-JSON body (e.g. SPA HTML when the Base URL
                    # points at the web-UI host instead of the API host) means we
                    # reached the wrong endpoint — treat it as CannotConnect.
                    return await resp.json()
        except (ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
            raise CannotConnect from err
