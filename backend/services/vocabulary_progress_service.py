"""
Vocabulary Growth Drill-down — PDG-US-12.

Per-word usage counters that back the Mastered (useCount >= 3) / Learning
(1-2) lists. `record_usage` is called from scenario_service.end_session right
after its existing vocab-coverage grading — no separate grading pass, this
just persists what that grading already decided.
"""

import logging
import re
from typing import Dict, List, Optional

from fastapi import Depends

from lib.prisma_client import db
from middlewares.auth_middleware import require_auth

logger = logging.getLogger(__name__)

MASTERY_THRESHOLD = 3
DEFAULT_PAGE_SIZE = 50
_VOWEL_GROUPS = re.compile(r"[aeiouyAEIOUY]+")


def _phonetic_spelling(word: str) -> str:
    """Naive offline syllable-ish spelling shown as a visual fallback
    alongside TTS playback (E-02) — not real IPA, just a readable approximation."""
    syllables = _VOWEL_GROUPS.split(word)
    groups = _VOWEL_GROUPS.findall(word)
    parts: List[str] = []
    for i, consonants in enumerate(syllables):
        parts.append(consonants)
        if i < len(groups):
            parts.append(groups[i])
    joined = "".join(parts)
    chunks = [joined[i : i + 3] for i in range(0, len(joined), 3) if joined[i : i + 3]]
    return "-".join(chunks).upper() or word.upper()


async def record_usage(user_id: str, words_used: List[str], words_missed: List[str]) -> None:
    for word in words_used:
        key = word.lower().strip()
        if not key:
            continue
        existing = await db.vocabularywordprogress.find_unique(
            where={"userId_word": {"userId": user_id, "word": key}}
        )
        new_count = (existing.useCount if existing else 0) + 1
        status = "mastered" if new_count >= MASTERY_THRESHOLD else "learning"
        await db.vocabularywordprogress.upsert(
            where={"userId_word": {"userId": user_id, "word": key}},
            data={
                "create": {"userId": user_id, "word": key, "useCount": 1, "status": status},
                "update": {
                    "useCount": new_count,
                    "status": status,
                    # A successful reuse resolves any earlier de-ranking flag.
                    "needsReview": False,
                },
            },
        )

    # E-03: a word already Mastered gets targeted again but missed this time.
    for word in words_missed:
        key = word.lower().strip()
        if not key:
            continue
        existing = await db.vocabularywordprogress.find_unique(
            where={"userId_word": {"userId": user_id, "word": key}}
        )
        if existing and existing.status == "mastered":
            await db.vocabularywordprogress.update(
                where={"userId_word": {"userId": user_id, "word": key}},
                data={"needsReview": True},
            )


def _serialize(row) -> Dict:
    return {
        "word": row.word,
        "use_count": row.useCount,
        "status": row.status,
        "needs_review": row.needsReview,
        "last_used_at": row.lastUsedAt.isoformat(),
        "phonetic_spelling": _phonetic_spelling(row.word),
    }


# ── Controllers ───────────────────────────────────────────────────────────────
async def get_drill_down(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_id: str = Depends(require_auth),
):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    total = await db.vocabularywordprogress.count(where={"userId": user_id})
    if total == 0:
        # E-01: Day 1 empty state — nothing collected yet.
        return {
            "is_empty_state": True,
            "mastered_count": 0,
            "learning_count": 0,
            "words": [],
            "page": 1,
            "page_size": page_size,
            "has_more": False,
        }

    mastered_count = await db.vocabularywordprogress.count(
        where={"userId": user_id, "status": "mastered"}
    )
    learning_count = total - mastered_count

    where = {"userId": user_id}
    if status in ("mastered", "learning"):
        where["status"] = status

    rows = await db.vocabularywordprogress.find_many(
        where=where,
        order={"lastUsedAt": "desc"},
        skip=(page - 1) * page_size,
        take=page_size,
    )
    filtered_total = mastered_count if status == "mastered" else learning_count if status == "learning" else total

    return {
        "is_empty_state": False,
        "mastered_count": mastered_count,
        "learning_count": learning_count,
        "words": [_serialize(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < filtered_total,
    }


async def get_word_detail(word: str, user_id: str = Depends(require_auth)):
    from fastapi.responses import JSONResponse

    key = word.lower().strip()
    row = await db.vocabularywordprogress.find_unique(
        where={"userId_word": {"userId": user_id, "word": key}}
    )
    if not row:
        return JSONResponse(status_code=404, content={"error": "Word not found in your vocabulary history"})
    return _serialize(row)
