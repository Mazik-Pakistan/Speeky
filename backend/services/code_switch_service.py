"""
Code-Switch Word List Service (US-152).

Thin service layer between the router and word_list_store. Handles the
empty-state message (E-03) and serialization to the response schema.
"""

from typing import List

from lib.code_switch.word_list_store import CodeSwitchWordListStore
from schemas.code_switch_schemas import (
    CodeSwitchedWordSchema,
    CodeSwitchWordListResponseSchema,
)

EMPTY_STATE_MESSAGE = (
    "Great job maintaining pure English! "
    "Words will appear here if you accidentally mix languages."
)

# Singleton store — same lazy-init pattern as other services.
_store = CodeSwitchWordListStore()


async def get_word_list(user_id: str) -> CodeSwitchWordListResponseSchema:
    """
    Returns sorted word list (E-02: by frequency desc).
    Returns empty state message when no words exist (E-03).
    """
    words = await _store.get_list(user_id)
    word_schemas = [
        CodeSwitchedWordSchema(
            word=w.word,
            english_equivalent=w.english_equivalent,
            context_sentences=w.context_sentences,
            frequency=w.frequency,
            ignored=w.ignored,
            first_seen=w.first_seen,
        )
        for w in words
    ]
    return CodeSwitchWordListResponseSchema(
        words=word_schemas,
        total=len(word_schemas),
        empty_state_message=EMPTY_STATE_MESSAGE if not word_schemas else None,
    )


async def ignore_word(user_id: str, word: str) -> bool:
    """E-01: Mark word as ignored. Returns False if word not found."""
    return await _store.ignore_word(user_id, word)


async def remove_word(user_id: str, word: str) -> bool:
    """E-01: Hard-delete word. Returns False if word not found."""
    return await _store.remove_word(user_id, word)


async def log_detected_word(
    user_id: str,
    word: str,
    english_equivalent: str,
    context_sentence: str,
) -> None:
    """Called by conversation_service after TextCodeSwitchDetector flags a word."""
    await _store.log_word(user_id, word, english_equivalent, context_sentence)
