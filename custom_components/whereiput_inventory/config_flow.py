"""Config + options flow for the whereiput.it Inventory integration.

Config flow (validate-on-connect, D-07): a single user step prefills the base
URL to ``http://localhost:8088`` (self-host-first) and takes a read token.
URL policy (MITM mitigation T-17-07): the scheme must be ``http`` or ``https``
(anything else is rejected as ``invalid_url`` BEFORE any network call). ``http``
is allowed ONLY for local/private hosts (localhost, 127.0.0.0/8, ::1, ``*.local``,
and the RFC1918 private ranges); for any public host ``http`` is rejected as
``insecure_url`` so a bearer token never rides plaintext to a public host.
One live ``search`` validates the token: a 200 creates the entry, a 401/403
surfaces ``invalid_auth`` and a connection failure surfaces ``cannot_connect``.

Multiple entries are allowed (D-06): the unique_id is a HASH of base_url+token
(never the raw token — T-17-08), so distinct pairs each create an entry while an
identical pair aborts as ``already_configured``.

Options flow (D-08): lists the token's accessible areas (``me/areas``) and stores
an optional area filter (default = none).
"""

from __future__ import annotations

import hashlib
import ipaddress
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InventoryClient
from .const import CONF_AREAS, CONF_BASE_URL, CONF_TOKEN, DEFAULT_URL, DOMAIN
from .exceptions import CannotConnect, InvalidAuth


def _entry_unique_id(base_url: str, token: str) -> str:
    """Stable hash of base_url + token.

    Used as the config-entry unique_id so D-06 multi-entry de-dupes identical
    pairs WITHOUT ever storing the raw token (T-17-08).
    """
    digest = hashlib.sha256(f"{base_url}:{token}".encode()).hexdigest()
    return digest


def _is_local_or_private_host(host: str) -> bool:
    """True if ``host`` is a local/private address safe to reach over plain http.

    Local/private = ``localhost``, any ``*.local`` hostname (mDNS), loopback
    (127.0.0.0/8, ::1), or an RFC1918 private IPv4 range
    (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) and IPv6 private/link-local.
    Used to gate the http-only-for-local policy (T-17-07).
    """
    if not host:
        return False

    host = host.lower()
    # Strip an IPv6 literal's surrounding brackets, e.g. "[::1]".
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    if host == "localhost" or host.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A non-IP, non-local hostname (e.g. a public domain) is NOT local.
        return False

    return ip.is_loopback or ip.is_private or ip.is_link_local


class WhereIPutConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow for whereiput.it Inventory."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single setup step: prefilled base URL + token, validated on connect."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            token = user_input[CONF_TOKEN]

            # URL policy (T-17-07), enforced BEFORE any network call:
            #   - scheme must be http or https (else invalid_url);
            #   - https is always allowed;
            #   - http is allowed ONLY for a local/private host; for a public
            #     host http is rejected as insecure_url (no plaintext bearer
            #     token to a public host).
            parts = urlsplit(base_url)
            scheme = parts.scheme.lower()
            if scheme not in ("http", "https"):
                errors["base"] = "invalid_url"
            elif scheme == "http" and not _is_local_or_private_host(
                parts.hostname or ""
            ):
                errors["base"] = "insecure_url"
            else:
                client = InventoryClient(
                    async_get_clientsession(self.hass), base_url, token
                )
                try:
                    # Validate-on-connect (D-07): one live search, no entry on failure.
                    await client.search("test", per_page=1)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    # D-06: multi-entry — de-dupe on a HASH, never the raw token.
                    await self.async_set_unique_id(_entry_unique_id(base_url, token))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="whereiput.it",
                        data={CONF_BASE_URL: base_url, CONF_TOKEN: token},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WhereIPutOptionsFlow:
        """Return the options flow (area filter)."""
        return WhereIPutOptionsFlow()


class WhereIPutOptionsFlow(config_entries.OptionsFlow):
    """Options flow: pick an optional area filter from the token's areas (D-08).

    NOTE (2026): do NOT assign ``self.config_entry`` in ``__init__`` — HA provides
    it automatically; assigning it is deprecated and breaks newer cores.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """List the token's accessible areas and store the chosen ids."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        errors: dict[str, str] = {}
        options: dict[int, str] = {}
        client = InventoryClient(
            async_get_clientsession(self.hass),
            self.config_entry.data[CONF_BASE_URL],
            self.config_entry.data[CONF_TOKEN],
        )
        try:
            areas = await client.areas()
        except (CannotConnect, InvalidAuth):
            # Surface a form error instead of crashing the options dialog.
            errors["base"] = "cannot_connect"
        else:
            options = {area["id"]: area["name"] for area in areas.get("data", [])}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AREAS,
                    default=self.config_entry.options.get(CONF_AREAS, []),
                ): cv.multi_select(options),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
