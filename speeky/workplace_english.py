"""
FEATURE: Workplace English Coaching
Covers user stories:
  US-61  Email Writing Coach              (doc: US-026)
  US-62  Meeting Communication Coach      (doc: US-033)
  US-63  Client Communication Simulation  (doc: US-027)

Self-contained: models + business logic + routes all live in this one file
so this feature can be picked up and worked on independently of
interview_coach.py. Only depends on the shared app/core/ infra
(store, ai_client, config, exceptions).

Mount in app/main.py with:
    from app.features.workplace_english import router as workplace_english_router
    app.include_router(workplace_english_router)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.store import store
from app.core.ai_client import ai_client
from app.core.config import settings
from app.core.exceptions import SessionNotFoundError, InvalidSubmissionError

# ============================================================================
# MODELS
# ============================================================================

class ScenarioType(str, Enum):
    EMAIL = "email"
    MEETING = "meeting"
    CLIENT = "client"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


# --- US-61: Email Writing Coach ---

class StartEmailScenarioRequest(BaseModel):
    user_id: str
    prompt_topic: Optional[str] = Field(None, description="e.g. 'Email your manager about a delayed project'")


class EmailScenarioResponse(BaseModel):
    session_id: Optional[str] = None
    prompt: str
    started_at: datetime


class SubmitEmailDraftRequest(BaseModel):
    session_id: Optional[str] = None
    subject: str = ""
    body: str


class EmailFeedback(BaseModel):
    session_id: Optional[str] = None
    workplace_tone_score: int
    grammar_score: int
    flags: List[str] = Field(default_factory=list)
    polished_version: str
    tone_notes: List[str] = Field(default_factory=list)


# --- US-62: Meeting Communication Coach ---

class StartMeetingScenarioRequest(BaseModel):
    user_id: str
    objective: str = Field(..., description="e.g. 'Propose a new marketing budget'")


class MeetingScenarioResponse(BaseModel):
    session_id: Optional[str] = None
    agenda: str
    objective: str
    ongoing_discussion_snippet: str
    started_at: datetime


class InterjectRequest(BaseModel):
    session_id: Optional[str] = None
    spoken_text: str
    time_into_meeting_seconds: int = Field(0, description="How long the AI meeting ran before the user spoke up")
    response_duration_seconds: int = 0


class MeetingFeedback(BaseModel):
    session_id: Optional[str] = None
    polite_interruption_score: int
    idea_clarity_score: int
    context_adherence_score: int
    flags: List[str] = Field(default_factory=list)
    suggested_transition_phrases: List[str] = Field(default_factory=list)
    summary: str


# --- US-63: Client Communication Simulation ---

class StartClientScenarioRequest(BaseModel):
    user_id: str
    client_situation: str = Field(..., description="e.g. 'Client is upset about a missed delivery deadline'")


class ClientScenarioResponse(BaseModel):
    session_id: Optional[str] = None
    client_opening_message: str
    started_at: datetime


class ClientTurnRequest(BaseModel):
    session_id: Optional[str] = None
    user_message: str
    response_duration_seconds: int = 0


class ClientTurnResponse(BaseModel):
    session_id: Optional[str] = None
    client_reply: str
    client_mood: str  # "satisfied" | "neutral" | "frustrated"
    flags: List[str] = Field(default_factory=list)
    scenario_ended: bool = False


class ClientCommunicationFeedback(BaseModel):
    session_id: Optional[str] = None
    client_management_score: int
    active_listening_score: int
    vocabulary_usage_score: int
    flags: List[str] = Field(default_factory=list)
    summary: str


# ============================================================================
# SERVICE (business logic)
# ============================================================================

EMAIL_NS = "we_email_sessions"
MEETING_NS = "we_meeting_sessions"
CLIENT_NS = "we_client_sessions"

SLANG_MARKERS = ["thx", "bro", "yeah", "lol", "gonna", "wanna", "no worries", "hey guys", "asap!!"]
AGGRESSIVE_MARKERS = ["you didn't", "your fault", "unacceptable", "ridiculous", "useless"]
CODE_SWITCH_MARKERS = ["jaldi", "yaar", "theek hai", "acha"]

DEFAULT_EMAIL_PROMPT = "Email your manager about a delayed project."
MEETING_AGENDA = "Weekly Marketing Sync: review Q3 spend, align on Q4 priorities."
DISCUSSION_SNIPPET = (
    "...so that covers the current spend. Before we move to the next item, "
    "does anyone have something to add?"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _contains_any(text: str, markers: List[str]) -> bool:
    lowered = text.lower()
    return any(m in lowered for m in markers)


# --- US-61 service ---

def start_email_scenario(req: StartEmailScenarioRequest) -> EmailScenarioResponse:
    session_id = _new_id("email")
    now = _now()
    prompt = req.prompt_topic or DEFAULT_EMAIL_PROMPT
    store.create(EMAIL_NS, session_id, {"session_id": session_id, "user_id": req.user_id, "prompt": prompt, "started_at": now})
    return EmailScenarioResponse(session_id=session_id, prompt=prompt, started_at=now)


def submit_email_draft(req: SubmitEmailDraftRequest) -> EmailFeedback:
    session = store.get(EMAIL_NS, req.session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {req.session_id} not found")

    if len(req.body.strip()) < settings.MIN_SUBMISSION_CHARS:  # E-03: blank/near-blank
        raise InvalidSubmissionError(f"Email body must be at least {settings.MIN_SUBMISSION_CHARS} characters.")

    flags: List[str] = []
    tone_notes: List[str] = []
    tone_score = 90
    grammar_score = 90

    if _contains_any(req.body, AGGRESSIVE_MARKERS):  # E-01: aggressive/accusatory tone
        flags.append("aggressive_tone")
        tone_notes.append("Accusatory phrasing detected — reframe diplomatically.")
        tone_score = min(tone_score, settings.TONE_FLAG_SCORE_CEILING)

    if _contains_any(req.body, SLANG_MARKERS):
        flags.append("informal_tone")
        tone_notes.append("Casual/slang language is not appropriate for a professional email.")
        tone_score = min(tone_score, settings.TONE_FLAG_SCORE_CEILING)

    if _contains_any(req.body, CODE_SWITCH_MARKERS):
        flags.append("code_switching")
        tone_notes.append("Mixed-language phrasing detected — use the English equivalent for workplace writing.")

    if not req.subject.strip():
        flags.append("missing_subject")
        tone_notes.append("A professional email needs a clear subject line.")

    polished = ai_client.generate(
        system_prompt=(
            "You are a workplace-English writing coach. Rewrite the user's email to be "
            "clear, professional, and appropriately toned, preserving their intent."
        ),
        user_message=f"Subject: {req.subject}\n\n{req.body}",
    )

    store.update(EMAIL_NS, req.session_id, {**session, "status": "completed"})

    return EmailFeedback(
        session_id=req.session_id, workplace_tone_score=tone_score, grammar_score=grammar_score,
        flags=flags, polished_version=polished, tone_notes=tone_notes,
    )


# --- US-62 service ---

def start_meeting_scenario(req: StartMeetingScenarioRequest) -> MeetingScenarioResponse:
    session_id = _new_id("meet")
    now = _now()
    store.create(MEETING_NS, session_id, {
        "session_id": session_id, "user_id": req.user_id, "objective": req.objective,
        "started_at": now, "interjected": False,
    })
    return MeetingScenarioResponse(
        session_id=session_id, agenda=MEETING_AGENDA, objective=req.objective,
        ongoing_discussion_snippet=DISCUSSION_SNIPPET, started_at=now,
    )


def interject(req: InterjectRequest) -> MeetingFeedback:
    session = store.get(MEETING_NS, req.session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {req.session_id} not found")

    flags: List[str] = []
    polite_score, clarity_score, context_score = 85, 85, 85
    suggestions: List[str] = []

    if not req.spoken_text.strip():  # E-01: never interjected (timeout)
        flags.append("missed_opportunity")
        return MeetingFeedback(
            session_id=req.session_id, polite_interruption_score=0, idea_clarity_score=0, context_adherence_score=0,
            flags=flags, suggested_transition_phrases=["If I could just jump in here...", "Could I add a quick point?"],
            summary="You did not interject during the meeting. Practice confidently stepping into the discussion.",
        )

    abrupt_markers = ["wait wait", "no listen", "stop", "shut"]
    if req.time_into_meeting_seconds < 2 or _contains_any(req.spoken_text, abrupt_markers):  # E-02
        flags.append("abrupt_interruption")
        polite_score = 30
        suggestions.append("If I could just jump in here...")

    if req.response_duration_seconds > settings.RAMBLING_SECONDS_THRESHOLD:  # E-03
        flags.append("rambling")
        clarity_score = 40

    objective_keywords = set(session["objective"].lower().split())  # E-04: off-agenda
    spoken_keywords = set(req.spoken_text.lower().split())
    if not objective_keywords & spoken_keywords:
        flags.append("off_agenda")
        context_score = 35

    summary = "Clear, well-timed contribution." if not flags else "Some areas to refine before your next meeting."

    session["interjected"] = True
    store.update(MEETING_NS, req.session_id, session)

    return MeetingFeedback(
        session_id=req.session_id, polite_interruption_score=polite_score, idea_clarity_score=clarity_score,
        context_adherence_score=context_score, flags=flags,
        suggested_transition_phrases=suggestions or ["Building on that point..."], summary=summary,
    )


# --- US-63 service ---

def start_client_scenario(req: StartClientScenarioRequest) -> ClientScenarioResponse:
    session_id = _new_id("client")
    now = _now()
    opening = ai_client.generate(
        system_prompt=(
            "You are role-playing an unhappy client in a workplace-English coaching "
            f"simulation. Open the conversation describing this situation: {req.client_situation}"
        ),
        user_message="Open the conversation.",
    )
    store.create(CLIENT_NS, session_id, {
        "session_id": session_id, "user_id": req.user_id, "situation": req.client_situation,
        "started_at": now, "mood": "neutral", "turns": 0, "monologue_flags": 0,
    })
    return ClientScenarioResponse(session_id=session_id, client_opening_message=opening, started_at=now)


def client_turn(req: ClientTurnRequest) -> ClientTurnResponse:
    session = store.get(CLIENT_NS, req.session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {req.session_id} not found")

    flags: List[str] = []
    mood = session["mood"]
    ended = False

    argumentative_markers = ["that's not my problem", "you're wrong", "whatever", "i don't care"]
    if _contains_any(req.user_message, argumentative_markers):  # E-01
        flags.append("argumentative")
        mood = "frustrated"
        ended = True

    overpromise_markers = ["guarantee", "definitely by tomorrow", "no problem at all, anything"]
    if _contains_any(req.user_message, overpromise_markers):  # E-02
        flags.append("over_promising")

    if req.response_duration_seconds > settings.RAMBLING_SECONDS_THRESHOLD:  # E-03
        session["monologue_flags"] += 1
        flags.append("long_monologue")

    non_ascii_ratio = sum(1 for ch in req.user_message if ord(ch) > 127) / max(len(req.user_message), 1)  # E-04
    if non_ascii_ratio > 0.3:
        flags.append("non_english_input")

    if not flags:
        mood = "satisfied" if session["turns"] >= 2 else "neutral"

    client_reply = ai_client.generate(
        system_prompt=f"You are a client with mood '{mood}' in situation: {session['situation']}. React realistically to the user's message.",
        user_message=req.user_message,
    )

    session["turns"] += 1
    session["mood"] = mood
    if ended:
        session["status"] = "completed"
    store.update(CLIENT_NS, req.session_id, session)

    return ClientTurnResponse(session_id=req.session_id, client_reply=client_reply, client_mood=mood, flags=flags, scenario_ended=ended)


def end_client_scenario(session_id: str) -> ClientCommunicationFeedback:
    session = store.get(CLIENT_NS, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    listening_score = max(90 - (session["monologue_flags"] * 20), 10)
    management_score = 90 if session["mood"] == "satisfied" else 50 if session["mood"] == "neutral" else 20

    return ClientCommunicationFeedback(
        session_id=session_id, client_management_score=management_score, active_listening_score=listening_score,
        vocabulary_usage_score=75, flags=[], summary=f"Client ended the scenario feeling '{session['mood']}'.",
    )


# ============================================================================
# ROUTES
# ============================================================================

router = APIRouter(prefix="/workplace-english", tags=["Workplace English Coaching"])


# --- US-61: Email Writing Coach ---
@router.post("/email/sessions", response_model=EmailScenarioResponse, status_code=201)
def api_start_email_scenario(req: StartEmailScenarioRequest):
    return start_email_scenario(req)


@router.post("/email/sessions/{session_id}/submit", response_model=EmailFeedback)
def api_submit_email_draft(session_id: str, req: SubmitEmailDraftRequest):
    req.session_id = session_id
    return submit_email_draft(req)


# --- US-62: Meeting Communication Coach ---
@router.post("/meeting/sessions", response_model=MeetingScenarioResponse, status_code=201)
def api_start_meeting_scenario(req: StartMeetingScenarioRequest):
    return start_meeting_scenario(req)


@router.post("/meeting/sessions/{session_id}/interject", response_model=MeetingFeedback)
def api_interject(session_id: str, req: InterjectRequest):
    req.session_id = session_id
    return interject(req)


# --- US-63: Client Communication Simulation ---
@router.post("/client/sessions", response_model=ClientScenarioResponse, status_code=201)
def api_start_client_scenario(req: StartClientScenarioRequest):
    return start_client_scenario(req)


@router.post("/client/sessions/{session_id}/turn", response_model=ClientTurnResponse)
def api_client_turn(session_id: str, req: ClientTurnRequest):
    req.session_id = session_id
    return client_turn(req)


@router.post("/client/sessions/{session_id}/end", response_model=ClientCommunicationFeedback)
def api_end_client_scenario(session_id: str):
    return end_client_scenario(session_id)


# ===========================================================================
# STANDALONE RUNNER
# Lets you run JUST this feature on its own, without the rest of the app:
#   uvicorn app.features.workplace_english:app --reload --port 8002
# main.py mounts `router` into the combined app instead of this `app`.
# ===========================================================================

from fastapi import FastAPI
from app.core.exceptions import install_error_handlers

app = FastAPI(title="Speeky - Workplace English Coaching")
install_error_handlers(app)
app.include_router(router)
