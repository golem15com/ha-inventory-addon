"""Offline EN+PL "where is X" ConversationEntity (D-01 #2, HACS-04).

This is the integration's ONLY entity, and it controls no devices
(``ConversationEntityFeature(0)``). It matches "where is X" / "gdzie jest X"
in-process with ``hassil`` over the bundled ``intents/{en,pl}.yaml`` (the
default agent cannot load integration-bundled sentences — RESEARCH Pitfall 1),
then answers a terse "name — location, area".

Rows are fetched per-call from the shared :class:`InventoryClient` and discarded
once the speech is rendered — inventory never enters any persisted context.
The per-entry area filter narrows scope only (D-08 / T-17-13).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from hassil import Intents, recognize

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import InventoryClient
from .const import DOMAIN
from .exceptions import CannotConnect, InvalidAuth

_SUPPORTED_LANGUAGES = ["en", "pl"]
_INTENTS_DIR = Path(__file__).parent / "intents"


@lru_cache(maxsize=len(_SUPPORTED_LANGUAGES))
def _load_intents(language: str) -> Intents:
    """Load + compile the bundled sentence YAML for a language (cached)."""
    path = _INTENTS_DIR / f"{language}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Intents.from_dict(data)


def _match_item(text: str, language: str) -> str | None:
    """Return the matched ``item`` slot, or None if the sentence is unhandled."""
    if language not in _SUPPORTED_LANGUAGES:
        return None
    result = recognize(text, _load_intents(language))
    if result is None:
        return None
    entity = result.entities.get("item")
    if entity is None:
        return None
    value = str(entity.value).strip()
    return value or None


def _terse_answer(rows: list[dict[str, Any]], item: str, language: str) -> str:
    """Render the terse "name — location, area" answer (EN/PL)."""
    if not rows:
        if language == "pl":
            return f'Nie znalazłem „{item}".'
        return f'I couldn\'t find "{item}".'

    row = rows[0]
    name = row.get("name") or item
    location = (row.get("location") or {}).get("name")
    area = (row.get("area") or {}).get("name")
    quantity = row.get("quantity")

    unknown = "nieznana lokalizacja" if language == "pl" else "unknown location"
    where = location or unknown
    if area:
        where = f"{where}, {area}"

    answer = f"{name} — {where}."
    if quantity and int(quantity) > 1:
        answer += f" Sztuk: {quantity}." if language == "pl" else f" Qty: {quantity}."
    return answer


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation entity for a config entry."""
    async_add_entities([WhereIPutConversationEntity(entry)])


class WhereIPutConversationEntity(conversation.ConversationEntity):
    """Offline EN+PL "where is X" conversation agent (no entity control)."""

    _attr_supported_features = conversation.ConversationEntityFeature(0)
    _attr_has_entity_name = True
    _attr_name = "whereiput.it"

    def __init__(self, entry: ConfigEntry) -> None:
        """Bind the owning config entry."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str]:
        """The offline fast-path covers EN + PL."""
        return _SUPPORTED_LANGUAGES

    def _entry_data(self) -> dict[str, Any]:
        return self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Match "where is X" and answer terse; fall through otherwise."""
        language = user_input.language or "en"
        response = intent.IntentResponse(language=language)

        item = _match_item(user_input.text, language)
        if item is None:
            # Not a "where is X" sentence — report no match so a downstream agent
            # (or the user) can take over.
            response.async_set_error(
                intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                "Sorry, I can only answer where an item is stored.",
            )
            return conversation.ConversationResult(
                response=response, conversation_id=user_input.conversation_id
            )

        entry_data = self._entry_data()
        client: InventoryClient | None = entry_data.get("client")
        if client is None:
            response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                "The inventory integration is not loaded.",
            )
            return conversation.ConversationResult(
                response=response, conversation_id=user_input.conversation_id
            )

        try:
            data = await client.search(
                item, per_page=1, areas=entry_data.get("areas") or None
            )
        except (CannotConnect, InvalidAuth):
            response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                "I couldn't reach the inventory server.",
            )
            return conversation.ConversationResult(
                response=response, conversation_id=user_input.conversation_id
            )

        speech = _terse_answer(data.get("data", []), item, language)
        response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=response, conversation_id=user_input.conversation_id
        )
