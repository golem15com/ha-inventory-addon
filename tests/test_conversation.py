"""Tests for the offline EN+PL "where is X" ConversationEntity (Plan 04).

The entity matches sentences in-process with hassil over the bundled
intents/{en,pl}.yaml (NOT the default agent), then answers a terse
"name — location, area" using the shared client. It is the integration's only
entity and controls no devices. The service (Task 1) is the primary CI surface;
these tests keep the conversation contract minimal but real.
"""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.whereiput_inventory import conversation as conv
from custom_components.whereiput_inventory.conversation import (
    WhereIPutConversationEntity,
)


def test_conversation_entity_supports_en_and_pl() -> None:
    """The conversation entity advertises EN + PL as supported languages."""
    entity = WhereIPutConversationEntity.__new__(WhereIPutConversationEntity)
    assert set(entity.supported_languages) >= {"en", "pl"}


def test_pl_match_extracts_item_slot() -> None:
    """'gdzie jest młotek' → item == 'młotek' via the bundled PL sentences."""
    assert conv._match_item("gdzie jest młotek", "pl") == "młotek"
    assert conv._match_item("znajdź młotek", "pl") == "młotek"


def test_en_match_extracts_item_slot() -> None:
    """'where is the hammer' → an item string via the bundled EN sentences."""
    assert conv._match_item("where is the hammer", "en") == "hammer"
    assert conv._match_item("find batteries", "en") == "batteries"


def test_unrelated_sentence_does_not_match() -> None:
    """A non 'where is X' sentence returns None (falls through)."""
    assert conv._match_item("what is the weather", "en") is None
    assert conv._match_item("jaka jest pogoda", "pl") is None


def test_terse_answer_contains_location_and_area() -> None:
    """The rendered answer joins name — location, area."""
    rows = [
        {
            "name": "młotek",
            "location": {"name": "Szuflada"},
            "area": {"name": "Garaż"},
            "quantity": 2,
        }
    ]
    answer = conv._terse_answer(rows, "młotek", "pl")
    assert "młotek" in answer
    assert "Szuflada" in answer
    assert "Garaż" in answer
    assert "—" in answer
    # quantity > 1 surfaces the count
    assert "Sztuk: 2" in answer


def test_terse_answer_empty_case() -> None:
    """No rows → the localized 'not found' phrasing."""
    assert "Nie znalazłem" in conv._terse_answer([], "śrubokręt", "pl")
    assert "couldn't find" in conv._terse_answer([], "screwdriver", "en")


async def test_handle_message_searches_and_answers() -> None:
    """A matched message searches once and renders a terse answer."""
    entity = WhereIPutConversationEntity.__new__(WhereIPutConversationEntity)

    mock_client = AsyncMock()
    mock_client.search.return_value = {
        "data": [
            {
                "name": "hammer",
                "location": {"name": "Drawer"},
                "area": {"name": "Garage"},
                "quantity": 1,
            }
        ],
        "meta": {},
    }
    entry_data = {"client": mock_client, "areas": [7]}

    user_input = _user_input("where is the hammer", "en")

    with patch.object(entity, "_entry_data", return_value=entry_data):
        result = await entity._async_handle_message(user_input, None)

    mock_client.search.assert_awaited_once()
    # the area filter is passed through (narrowing only)
    assert mock_client.search.await_args.kwargs.get("areas") == [7]
    speech = result.response.speech["plain"]["speech"]
    assert "Drawer" in speech
    assert "Garage" in speech


def _user_input(text: str, language: str):
    from homeassistant.components import conversation
    from homeassistant.core import Context

    return conversation.ConversationInput(
        text=text,
        context=Context(),
        conversation_id=None,
        device_id=None,
        satellite_id=None,
        language=language,
        agent_id="conversation.whereiput_it",
    )
