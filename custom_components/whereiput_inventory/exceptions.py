"""Exceptions for the whereiput.it Inventory integration."""

from homeassistant.exceptions import HomeAssistantError


class InvalidAuth(HomeAssistantError):
    """Raised when the API token is rejected (HTTP 401/403)."""


class CannotConnect(HomeAssistantError):
    """Raised on any other failure: non-200 response, network error, timeout."""
