# Wave 0 RED — GREEN in Plan 04
"""RED stub: ConversationEntity surface contract.

Imports the not-yet-built conversation module and asserts the entity exposes
the EN+PL "where is X" offline fast-path surface. Plan 04 turns this GREEN.
"""

import pytest

from custom_components.whereiput_inventory.conversation import (  # noqa: F401
    WhereIPutConversationEntity,
)


def test_conversation_entity_supports_en_and_pl() -> None:
    """The conversation entity advertises EN + PL as supported languages."""
    entity = WhereIPutConversationEntity.__new__(WhereIPutConversationEntity)
    assert set(entity.supported_languages) >= {"en", "pl"}
