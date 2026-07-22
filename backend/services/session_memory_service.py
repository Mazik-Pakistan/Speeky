"""
Session & Memory Handling (US-28): interruption/auto-resume + cross-session
personalization memory. Ported from speeky/session_memory.py into backend conventions
(kv_store persistence, require_auth, ai_client). Cross-cutting: it wraps around sessions
created by other features, so session_type stays a free string. All records are scoped to
the authenticated user; the memory profile is keyed by user id.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends

from lib import ai_client, kv_store
from middlewares.auth_middleware import require_auth
from schemas.session_memory_schemas import (
    InterruptionResponse,
    InterruptionStatus,
    InterruptionStatusResponse,
    LogInterruptionRequest,
    MemoryProfile,
    PersonalizedOpeningResponse,
    RecordSessionRequest,
    ResumeRequest,
    ResumeResponse,
)
from utils.feature_errors import SessionNotFoundError

INTERRUPTIONS_NS = "session_memory_interruptions"
MEMORY_NS = "session_memory_profiles"

STALE_RESUME_THRESHOLD_MINUTES = 60  # E-02

# Flags counted as "weaknesses" for cross-session memory (mirrors flags emitted by
# interview_coach / coaching services).
WEAKNESS_FLAGS = {
    "rambling", "one_word_answer", "jumped_to_number", "aggressive_tone",
    "informal_tone", "abrupt_interruption", "off_agenda", "argumentative",
    "over_promising", "long_monologue", "missed_opportunity", "prolonged_silence",
    "vague_technical_answer",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── US-28 interruption & auto-resume ──────────────────────────────────────────
async def _user_interruptions(user_id: str, session_id: str) -> List[Dict]:
    return [
        v for v in await kv_store.store.list_values(INTERRUPTIONS_NS)
        if v["session_id"] == session_id and v.get("user_id") == user_id
    ]


async def _latest_interruption(user_id: str, session_id: str) -> Optional[Dict]:
    matches = await _user_interruptions(user_id, session_id)
    return max(matches, key=lambda v: v["logged_at"]) if matches else None


async def _log_interruption(user_id: str, req: LogInterruptionRequest) -> InterruptionResponse:
    """E-01: partial_answer_text preserves in-progress input. E-03: count tracks repeats."""
    now = _now()
    interruption_id = _new_id("intr")
    count = len(await _user_interruptions(user_id, req.session_id)) + 1
    await kv_store.store.create(INTERRUPTIONS_NS, interruption_id, {
        "interruption_id": interruption_id, "user_id": user_id, "session_id": req.session_id,
        "session_type": req.session_type, "interruption_type": req.interruption_type,
        "partial_answer_text": req.partial_answer_text, "status": InterruptionStatus.ACTIVE,
        "logged_at": now,
    })
    return InterruptionResponse(
        interruption_id=interruption_id, session_id=req.session_id,
        status=InterruptionStatus.ACTIVE, interruption_count_this_session=count, logged_at=now,
    )


async def _get_interruption_status(user_id: str, session_id: str) -> InterruptionStatusResponse:
    matches = await _user_interruptions(user_id, session_id)
    latest = max(matches, key=lambda v: v["logged_at"]) if matches else None
    has_active = latest is not None and latest["status"] == InterruptionStatus.ACTIVE
    return InterruptionStatusResponse(
        session_id=session_id, has_active_interruption=has_active,
        interruption_count_this_session=len(matches),
        last_interruption_at=latest["logged_at"] if latest else None,
    )


async def _resume_session(user_id: str, session_id: str) -> ResumeResponse:
    """E-02: stale if too much wall-clock passed. E-05: carries partial_answer_text back."""
    latest = await _latest_interruption(user_id, session_id)
    if latest is None:
        raise SessionNotFoundError(f"No interruption on record for session {session_id}")

    if latest["status"] == InterruptionStatus.RESUMED:
        return ResumeResponse(
            session_id=session_id, status=InterruptionStatus.RESUMED, partial_answer_text=None,
            stale=False, message="Session was already resumed — nothing pending.",
        )

    if _now() - latest["logged_at"] > timedelta(minutes=STALE_RESUME_THRESHOLD_MINUTES):
        latest["status"] = InterruptionStatus.STALE
        await kv_store.store.update(INTERRUPTIONS_NS, latest["interruption_id"], latest)
        return ResumeResponse(
            session_id=session_id, status=InterruptionStatus.STALE, partial_answer_text=None, stale=True,
            message=(f"This session was interrupted over {STALE_RESUME_THRESHOLD_MINUTES} minutes ago. "
                     "Resuming into stale state isn't offered — start fresh instead."),
        )

    latest["status"] = InterruptionStatus.RESUMED
    await kv_store.store.update(INTERRUPTIONS_NS, latest["interruption_id"], latest)
    return ResumeResponse(
        session_id=session_id, status=InterruptionStatus.RESUMED,
        partial_answer_text=latest.get("partial_answer_text"), stale=False,
        message="Resumed — any in-progress answer has been restored.",
    )


# ── US-28 cross-session personalization memory ────────────────────────────────
async def _record_session(user_id: str, req: RecordSessionRequest) -> MemoryProfile:
    existing = await kv_store.store.get(MEMORY_NS, user_id)
    profile = existing if existing is not None else {"user_id": user_id, "sessions": []}
    profile["sessions"].append({
        "session_id": req.session_id, "session_type": req.session_type,
        "flags_seen": req.flags_seen, "topic_or_mode": req.topic_or_mode,
        "overall_score": req.overall_score, "recorded_at": _now().isoformat(),
    })
    if existing is None:
        await kv_store.store.create(MEMORY_NS, user_id, profile)
    else:
        await kv_store.store.update(MEMORY_NS, user_id, profile)
    return await _build_memory_profile(user_id)


async def _build_memory_profile(user_id: str) -> MemoryProfile:
    raw = await kv_store.store.get(MEMORY_NS, user_id)
    if raw is None:
        return MemoryProfile(
            user_id=user_id, sessions_recorded=0, recurring_weaknesses=[],
            recurring_strengths=[], recent_topics=[], last_updated=_now(),
        )
    sessions = raw["sessions"]
    recent = sessions[-10:]  # most recent sessions weighted more

    flag_counts: Dict[str, int] = {}
    for s in recent:
        for f in s.get("flags_seen", []):
            flag_counts[f] = flag_counts.get(f, 0) + 1
    recurring_weaknesses = sorted(
        [f for f, c in flag_counts.items() if f in WEAKNESS_FLAGS and c >= 2],
        key=lambda f: -flag_counts[f],
    )
    strength_topics = [
        s["topic_or_mode"] for s in recent
        if s.get("overall_score") is not None and s["overall_score"] >= 80 and s.get("topic_or_mode")
    ]
    recurring_strengths = sorted(set(strength_topics))
    recent_topics = [s["topic_or_mode"] for s in recent if s.get("topic_or_mode")]

    return MemoryProfile(
        user_id=user_id, sessions_recorded=len(sessions),
        recurring_weaknesses=recurring_weaknesses, recurring_strengths=recurring_strengths,
        recent_topics=recent_topics[-5:], last_updated=_now(),
    )


async def _get_personalized_opening(user_id: str) -> PersonalizedOpeningResponse:
    """E-04: no prior sessions -> generic opening, no fabricated personalization."""
    profile = await _build_memory_profile(user_id)
    if profile.sessions_recorded == 0:
        return PersonalizedOpeningResponse(
            user_id=user_id, has_history=False,
            opening_message="Welcome! Let's get started with your first practice session.",
        )
    weaknesses = ", ".join(profile.recurring_weaknesses) or "no major recurring issues"
    strengths = ", ".join(profile.recurring_strengths) or "still building a track record"
    opening = await ai_client.generate(
        system_prompt=(
            "You are a supportive interview/communication coach welcoming back a returning user. "
            f"Write ONE short, warm sentence referencing their recurring weak areas ({weaknesses}) "
            f"and strengths ({strengths}) from past sessions, to set focus for today. "
            "No preamble, just the sentence."
        ),
        user_message=f"Recent topics practiced: {', '.join(profile.recent_topics) or 'none recorded'}.",
        max_tokens=150,
    )
    return PersonalizedOpeningResponse(user_id=user_id, has_history=True, opening_message=opening)


# ── controllers (auth-gated) ──────────────────────────────────────────────────
async def log_interruption(payload: LogInterruptionRequest, user_id: str = Depends(require_auth)):
    return await _log_interruption(user_id, payload)


async def get_interruption_status(session_id: str, user_id: str = Depends(require_auth)):
    return await _get_interruption_status(user_id, session_id)


async def resume_session(payload: ResumeRequest, user_id: str = Depends(require_auth)):
    return await _resume_session(user_id, payload.session_id)


async def record_session(payload: RecordSessionRequest, user_id: str = Depends(require_auth)):
    return await _record_session(user_id, payload)


async def get_memory_profile(user_id: str = Depends(require_auth)):
    return await _build_memory_profile(user_id)


async def get_personalized_opening(user_id: str = Depends(require_auth)):
    return await _get_personalized_opening(user_id)
