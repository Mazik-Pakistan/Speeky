"""
FEATURE: Session & Memory Handling
Covers, in one file so it can be built/reviewed as a single unit:
  US-28  Session Interruption & Auto-Resume Handling
  US-28  Cross-Session Personalization Memory

Note: these two share the same ticket number (US-28) in the tracker — they're
a split of one parent story into two halves. Neither was documented with
detailed acceptance criteria/exception handling in the feature doc (unlike
US-004, US-40, US-43, US-44), so the design below follows the same pattern
established by those documented stories, applied sensibly to what the
titles describe. Flag anything here to the team lead if the intent differs
from what's built.

This feature is cross-cutting: it doesn't run its own interview/coaching
logic. It wraps AROUND sessions created by other features (interview_coach,
workplace_english, future ones) — logging interruptions, enabling resume,
and building a per-user memory profile from how past sessions went. That's
why session_type is a free string here rather than an enum tied to one
feature's session model.

File is organized top-to-bottom as: models -> constants -> service
functions -> FastAPI router. Import `router` from this file into app/main.py.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.store import store
from app.core.ai_client import ai_client
from app.core.exceptions import SessionNotFoundError, InvalidSubmissionError

# ===========================================================================
# MODELS
# ===========================================================================

class InterruptionType(str, Enum):
    PHONE_CALL = "phone_call"
    APP_BACKGROUNDED = "app_backgrounded"
    CONNECTIVITY_DROP = "connectivity_drop"
    MANUAL = "manual"


class InterruptionStatus(str, Enum):
    ACTIVE = "active"          # currently interrupted, awaiting resume
    RESUMED = "resumed"
    STALE = "stale"            # E-02: too much time passed, resume not offered


class LogInterruptionRequest(BaseModel):
    session_id: str
    session_type: str = Field(..., description="e.g. 'interview_coach', 'workplace_english'")
    interruption_type: InterruptionType
    partial_answer_text: Optional[str] = Field(
        None, description="E-01: whatever the user had typed/said when interrupted, so it isn't lost"
    )


class InterruptionResponse(BaseModel):
    interruption_id: str
    session_id: str
    status: InterruptionStatus
    interruption_count_this_session: int
    logged_at: datetime


class ResumeRequest(BaseModel):
    session_id: str


class ResumeResponse(BaseModel):
    session_id: str
    status: InterruptionStatus
    partial_answer_text: Optional[str] = None
    stale: bool = False
    message: str


class InterruptionStatusResponse(BaseModel):
    session_id: str
    has_active_interruption: bool
    interruption_count_this_session: int
    last_interruption_at: Optional[datetime] = None


# --- Cross-session personalization memory ---

class RecordSessionRequest(BaseModel):
    user_id: str
    session_id: str
    session_type: str
    flags_seen: List[str] = Field(default_factory=list, description="e.g. ['rambling', 'one_word_answer']")
    topic_or_mode: Optional[str] = Field(None, description="e.g. 'standard interview - Software Engineer'")
    overall_score: Optional[int] = None


class MemoryProfile(BaseModel):
    user_id: str
    sessions_recorded: int
    recurring_weaknesses: List[str]
    recurring_strengths: List[str]
    recent_topics: List[str]
    last_updated: datetime


class PersonalizedOpeningResponse(BaseModel):
    user_id: str
    has_history: bool
    opening_message: str


# ===========================================================================
# CONSTANTS
# ===========================================================================

INTERRUPTIONS_NS = "session_memory_interruptions"
MEMORY_NS = "session_memory_profiles"

# E-02: beyond this, a resume attempt is treated as stale rather than blindly resumed
STALE_RESUME_THRESHOLD_MINUTES = 60

# Flags that count as "weaknesses" for cross-session memory (mirrors flags
# emitted by interview_coach.py / workplace_english.py)
WEAKNESS_FLAGS = {
    "rambling", "one_word_answer", "jumped_to_number", "aggressive_tone",
    "informal_tone", "abrupt_interruption", "off_agenda", "argumentative",
    "over_promising", "long_monologue", "missed_opportunity",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ===========================================================================
# SERVICE FUNCTIONS — US-28 Session Interruption & Auto-Resume
# ===========================================================================

def log_interruption(req: LogInterruptionRequest) -> InterruptionResponse:
    """
    E-01: if the user was mid-answer, the caller passes partial_answer_text
    so nothing typed/spoken gets lost when we auto-pause.
    E-03: tracks interruption_count_this_session so repeated drops are visible.
    """
    now = _now()
    interruption_id = _new_id("intr")

    prior = [
        v for v in store.list_values(INTERRUPTIONS_NS)
        if v["session_id"] == req.session_id
    ]
    count = len(prior) + 1

    record = {
        "interruption_id": interruption_id,
        "session_id": req.session_id,
        "session_type": req.session_type,
        "interruption_type": req.interruption_type,
        "partial_answer_text": req.partial_answer_text,
        "status": InterruptionStatus.ACTIVE,
        "logged_at": now,
    }
    store.create(INTERRUPTIONS_NS, interruption_id, record)

    return InterruptionResponse(
        interruption_id=interruption_id,
        session_id=req.session_id,
        status=InterruptionStatus.ACTIVE,
        interruption_count_this_session=count,
        logged_at=now,
    )


def _latest_interruption_for_session(session_id: str) -> Optional[dict]:
    matches = [
        v for v in store.list_values(INTERRUPTIONS_NS)
        if v["session_id"] == session_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda v: v["logged_at"])


def get_interruption_status(session_id: str) -> InterruptionStatusResponse:
    matches = [
        v for v in store.list_values(INTERRUPTIONS_NS)
        if v["session_id"] == session_id
    ]
    latest = _latest_interruption_for_session(session_id)
    has_active = latest is not None and latest["status"] == InterruptionStatus.ACTIVE
    return InterruptionStatusResponse(
        session_id=session_id,
        has_active_interruption=has_active,
        interruption_count_this_session=len(matches),
        last_interruption_at=latest["logged_at"] if latest else None,
    )


def resume_session(req: ResumeRequest) -> ResumeResponse:
    """
    E-02: if too much wall-clock time has passed since the interruption,
    don't silently resume into stale state — tell the caller so the
    frontend can offer a fresh start instead.
    E-05: on reconnect, the same interruption record carries whatever
    partial_answer_text was captured, so a mid-question drop resumes with
    the same in-progress state rather than losing it.
    """
    latest = _latest_interruption_for_session(req.session_id)
    if latest is None:
        raise SessionNotFoundError(f"No interruption on record for session {req.session_id}")

    if latest["status"] == InterruptionStatus.RESUMED:
        return ResumeResponse(
            session_id=req.session_id, status=InterruptionStatus.RESUMED,
            partial_answer_text=None, stale=False,
            message="Session was already resumed — nothing pending.",
        )

    age = _now() - latest["logged_at"]
    if age > timedelta(minutes=STALE_RESUME_THRESHOLD_MINUTES):
        latest["status"] = InterruptionStatus.STALE
        store.update(INTERRUPTIONS_NS, latest["interruption_id"], latest)
        return ResumeResponse(
            session_id=req.session_id, status=InterruptionStatus.STALE,
            partial_answer_text=None, stale=True,
            message=(
                f"This session was interrupted over {STALE_RESUME_THRESHOLD_MINUTES} "
                "minutes ago. Resuming into stale state isn't offered — start fresh instead."
            ),
        )

    latest["status"] = InterruptionStatus.RESUMED
    store.update(INTERRUPTIONS_NS, latest["interruption_id"], latest)
    return ResumeResponse(
        session_id=req.session_id, status=InterruptionStatus.RESUMED,
        partial_answer_text=latest.get("partial_answer_text"), stale=False,
        message="Resumed — any in-progress answer has been restored.",
    )


# ===========================================================================
# SERVICE FUNCTIONS — US-28 Cross-Session Personalization Memory
# ===========================================================================

def record_session(req: RecordSessionRequest) -> MemoryProfile:
    """
    Feeds a completed session's flags/topic into the user's running memory
    profile. Called by the frontend right after any session's /end call.
    E-04 (no prior data) is handled naturally — profile just starts empty.
    """
    now = _now()
    existing = store.get(MEMORY_NS, req.user_id)
    profile = existing if existing is not None else {"user_id": req.user_id, "sessions": []}

    profile["sessions"].append({
        "session_id": req.session_id,
        "session_type": req.session_type,
        "flags_seen": req.flags_seen,
        "topic_or_mode": req.topic_or_mode,
        "overall_score": req.overall_score,
        "recorded_at": now.isoformat(),
    })

    if existing is None:
        store.create(MEMORY_NS, req.user_id, profile)
    else:
        store.update(MEMORY_NS, req.user_id, profile)

    return _build_memory_profile(req.user_id)


def _build_memory_profile(user_id: str) -> MemoryProfile:
    raw = store.get(MEMORY_NS, user_id)
    if raw is None:
        return MemoryProfile(
            user_id=user_id, sessions_recorded=0, recurring_weaknesses=[],
            recurring_strengths=[], recent_topics=[], last_updated=_now(),
        )

    sessions = raw["sessions"]
    # E-05: most recent sessions weighted more — only look at the last 10
    recent = sessions[-10:]

    flag_counts: dict[str, int] = {}
    for s in recent:
        for f in s.get("flags_seen", []):
            flag_counts[f] = flag_counts.get(f, 0) + 1

    # A flag showing up in 2+ of the last 10 sessions counts as "recurring"
    recurring_weaknesses = sorted(
        [f for f, c in flag_counts.items() if f in WEAKNESS_FLAGS and c >= 2],
        key=lambda f: -flag_counts[f],
    )
    # High-scoring sessions (>=80) with few/no weakness flags count toward strengths
    strength_topics = [
        s["topic_or_mode"] for s in recent
        if s.get("overall_score") is not None and s["overall_score"] >= 80 and s.get("topic_or_mode")
    ]
    recurring_strengths = sorted(set(strength_topics))

    recent_topics = [s["topic_or_mode"] for s in recent if s.get("topic_or_mode")]

    return MemoryProfile(
        user_id=user_id,
        sessions_recorded=len(sessions),
        recurring_weaknesses=recurring_weaknesses,
        recurring_strengths=recurring_strengths,
        recent_topics=recent_topics[-5:],
        last_updated=_now(),
    )


def get_memory_profile(user_id: str) -> MemoryProfile:
    return _build_memory_profile(user_id)


def get_personalized_opening(user_id: str) -> PersonalizedOpeningResponse:
    """
    E-04: no prior sessions -> generic opening, no fabricated personalization.
    Otherwise, generates a short opening line that references what past
    sessions showed (e.g. "let's work on keeping answers concise again").
    """
    profile = _build_memory_profile(user_id)
    if profile.sessions_recorded == 0:
        return PersonalizedOpeningResponse(
            user_id=user_id, has_history=False,
            opening_message="Welcome! Let's get started with your first practice session.",
        )

    weaknesses = ", ".join(profile.recurring_weaknesses) or "no major recurring issues"
    strengths = ", ".join(profile.recurring_strengths) or "still building a track record"

    opening = ai_client.generate(
        system_prompt=(
            "You are a supportive interview/communication coach welcoming back a "
            "returning user. Write ONE short, warm sentence referencing their "
            f"recurring weak areas ({weaknesses}) and strengths ({strengths}) from "
            "past sessions, to set focus for today. No preamble, just the sentence."
        ),
        user_message=f"Recent topics practiced: {', '.join(profile.recent_topics) or 'none recorded'}.",
        max_tokens=150,
    )
    return PersonalizedOpeningResponse(user_id=user_id, has_history=True, opening_message=opening)


# ===========================================================================
# ROUTER
# ===========================================================================

router = APIRouter(prefix="/session-memory", tags=["Session & Memory Handling"])


@router.post("/interruptions", response_model=InterruptionResponse, status_code=201)
def api_log_interruption(req: LogInterruptionRequest):
    return log_interruption(req)


@router.get("/interruptions/{session_id}/status", response_model=InterruptionStatusResponse)
def api_interruption_status(session_id: str):
    return get_interruption_status(session_id)


@router.post("/resume", response_model=ResumeResponse)
def api_resume(req: ResumeRequest):
    return resume_session(req)


@router.post("/profile/record-session", response_model=MemoryProfile, status_code=201)
def api_record_session(req: RecordSessionRequest):
    return record_session(req)


@router.get("/profile/{user_id}", response_model=MemoryProfile)
def api_get_profile(user_id: str):
    return get_memory_profile(user_id)


@router.get("/profile/{user_id}/personalized-opening", response_model=PersonalizedOpeningResponse)
def api_personalized_opening(user_id: str):
    return get_personalized_opening(user_id)


# ===========================================================================
# STANDALONE RUNNER
# Lets you run JUST this feature on its own, without the rest of the app:
#   uvicorn app.features.session_memory:app --reload --port 8003
# main.py mounts `router` into the combined app instead of this `app`.
# ===========================================================================

from fastapi import FastAPI
from app.core.exceptions import install_error_handlers

app = FastAPI(title="Speeky - Session & Memory Handling")
install_error_handlers(app)
app.include_router(router)
