"""
Progress Dashboard — PDG-US-14: Vocabulary Growth Tracker.

Aggregates existing per-feature scoring (BaselineAssessment, CoachingSession,
ScenarioSession — no new tables) into one dashboard view: vocabulary score
trend, newly-used vocabulary from the latest Scenario-Based Learning session,
cumulative practice time, and the latest confidence/fluency reading. Gated the
same way as every other GatedFeature (assessment required), reusing
gating_service rather than inventing a parallel access check.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends
from fastapi.responses import JSONResponse

from lib.prisma_client import db
from middlewares.auth_middleware import require_auth

logger = logging.getLogger(__name__)

# E-03: cap a single session's "new vocabulary" count so a scoring anomaly
# (or a model hallucination flagging ordinary words as new) can't skew the chart.
MAX_DAILY_VOCAB_GROWTH = 15

_EMPTY_STATE_MESSAGE = "Complete a Scenario to start collecting words!"
_ZERO_GROWTH_MESSAGE = "Great consistency! Try a new Scenario to discover advanced words."


def _session_record(completed_at: datetime, **scores: Optional[float]) -> Dict:
    return {"completed_at": completed_at, **scores}


async def _completed_records(user_id: str) -> List[Dict]:
    """Normalizes completed rows across the three scored feature tables into one
    timeline, so metric lookups don't need to special-case each source."""
    records: List[Dict] = []

    baselines = await db.baselineassessment.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}
    )
    for b in baselines:
        records.append(
            _session_record(
                b.completedAt,
                vocabulary_score=b.vocabularyScore,
                confidence_score=b.confidenceScore,
                fluency_score=b.fluencyScore,
                duration_seconds=(b.completedAt - b.startedAt).total_seconds(),
            )
        )

    coaching = await db.coachingsession.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}
    )
    for c in coaching:
        records.append(
            _session_record(
                c.completedAt,
                vocabulary_score=c.vocabularyScore,
                confidence_score=c.confidenceScore,
                fluency_score=c.fluencyScore,
                duration_seconds=(c.completedAt - c.createdAt).total_seconds(),
            )
        )

    scenarios = await db.scenariosession.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}
    )
    for s in scenarios:
        records.append(
            _session_record(
                s.completedAt,
                vocabulary_score=s.vocabularyScore,
                confidence_score=s.confidenceScore,
                fluency_score=None,  # ScenarioSession doesn't score fluency
                duration_seconds=(s.completedAt - s.createdAt).total_seconds(),
            )
        )

    records.sort(key=lambda r: r["completed_at"])
    return records


def _latest_metric(records: List[Dict], key: str) -> Optional[float]:
    for record in reversed(records):
        value = record.get(key)
        if value is not None:
            return round(value, 2)
    return None


async def _vocabulary_growth(user_id: str) -> Dict:
    sessions = await db.scenariosession.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "asc"}
    )
    if not sessions:
        return {
            "new_words_count": 0,
            "is_empty_state": True,
            "is_zero_growth": False,
            "message": _EMPTY_STATE_MESSAGE,
        }

    seen: set = set()
    for session in sessions[:-1]:
        seen.update(session.vocabUsed)

    latest_new_words = sorted(set(sessions[-1].vocabUsed) - seen)
    new_words_count = min(len(latest_new_words), MAX_DAILY_VOCAB_GROWTH)

    is_zero_growth = new_words_count == 0
    return {
        "new_words_count": new_words_count,
        "new_words": latest_new_words[:MAX_DAILY_VOCAB_GROWTH],
        "is_empty_state": False,
        "is_zero_growth": is_zero_growth,
        "message": _ZERO_GROWTH_MESSAGE if is_zero_growth else None,
    }


# ── Controller ────────────────────────────────────────────────────────────────
async def get_overview(user_id: str = Depends(require_auth)):
    from services.gating_service import GatedFeature, check_feature_access

    access = await check_feature_access(user_id, GatedFeature.PROGRESS_DASHBOARD.value)
    if not access["accessible"]:
        return JSONResponse(status_code=403, content={"error": access["reason"], "gating": access})

    records = await _completed_records(user_id)
    growth = await _vocabulary_growth(user_id)

    practice_time_minutes = round(
        sum(r["duration_seconds"] for r in records) / 60, 1
    )
    vocabulary_history = [
        {"date": r["completed_at"].isoformat(), "vocabulary_score": round(r["vocabulary_score"], 2)}
        for r in records
        if r.get("vocabulary_score") is not None
    ][-20:]  # cap chart payload to the most recent 20 points

    return {
        "has_data": bool(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "practice_time_minutes": practice_time_minutes,
            "confidence_score": _latest_metric(records, "confidence_score"),
            "fluency_score": _latest_metric(records, "fluency_score"),
            "vocabulary_score": _latest_metric(records, "vocabulary_score"),
        },
        "vocabulary_growth": growth,
        "vocabulary_history": vocabulary_history,
    }
