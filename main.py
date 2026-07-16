import os
import time
from datetime import date
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from openai import OpenAI, APITimeoutError
from dotenv import load_dotenv
from prompts import (
    build_system_prompt,
    TOPICS,
    build_interview_prompt,
    build_topic_validation_prompt,
    build_level_judge_prompt,
    VALID_LEVELS,
)

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

app = FastAPI()

# in-memory stores (v1 only — swap for DB later)
sessions = {}
daily_challenge = {}  # key: (session_id, date) -> accumulated seconds

# GAP-01: simple in-memory log of custom topics for future "recently practiced"
# suggestions. Stub only — same spirit as the Daily Challenge counter.
custom_topics_log = []  # list of {"session_id", "topic", "ts"}

# GAP-02: transcripts must survive past /chat/end (sessions dict gets popped
# there), so completed sessions are archived here for later review/replay.
# v1 in-memory only — no real 90-day retention window yet, that needs the DB.
transcript_store = {}  # session_id -> {"topic", "history", "ended_at"}


class ChatRequest(BaseModel):
    session_id: str
    topic: str          # key from TOPICS, e.g. "daily_life", or "custom"
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_duration_sec: float
    status: str = "ok"          # ok | timeout | error
    daily_challenge_sec: float = 0.0
    level: Optional[str] = None
    level_adjustment_note: Optional[str] = None


class StartResponse(BaseModel):
    status: str
    topic: str
    session_id: Optional[str] = None
    opening_message: Optional[str] = None
    needs_clarification: bool = False
    reason: Optional[str] = None
    level: Optional[str] = None
    level_note: Optional[str] = None


# ---------------------------------------------------------------------------
# GAP-01: Custom Topic validation (LLM-judged)
# ---------------------------------------------------------------------------

def validate_custom_topic(topic: str) -> dict:
    """Ask the LLM to judge a user-submitted custom topic.

    Returns dict: {"verdict": SAFE|UNSAFE|VAGUE, "preset_match": key|NONE, "reason": str}
    Fails open (SAFE/NONE) if the validation call itself errors out, so a flaky
    LLM call never silently blocks a legitimate custom topic session.
    """
    prompt = build_topic_validation_prompt(topic)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            timeout=10,
        )
        text = completion.choices[0].message.content.strip()
    except Exception:
        return {
            "verdict": "SAFE",
            "preset_match": "NONE",
            "reason": "validation service unavailable, defaulted to allow",
        }

    verdict = "SAFE"
    preset_match = "NONE"
    reason = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("PRESET_MATCH:"):
            preset_match = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    return {"verdict": verdict, "preset_match": preset_match, "reason": reason}


def judge_user_level(recent_messages: list) -> Optional[str]:
    """GAP-03: LLM-judged proficiency drift check, based on a rolling window of
    the user's last 3 turns. Fails closed (returns None -> no adjustment) on
    any error, so a flaky LLM call never causes a spurious level flip.
    """
    if not recent_messages:
        return None
    prompt = build_level_judge_prompt(recent_messages)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            timeout=10,
        )
        text = completion.choices[0].message.content.strip().lower()
    except Exception:
        return None

    for lvl in VALID_LEVELS:
        if lvl in text:
            return lvl
    return None


def resolve_level(level: Optional[str]):
    """GAP-03: figure out which proficiency level a session should start at.

    Returns (used_level, note). `level` simulates whatever the real Baseline
    Assessment / Confidence Score engine will eventually inject; this engine
    just consumes it.
    """
    level = level.lower() if level else None
    note = None

    if level in VALID_LEVELS:
        return level, note

    # E-01: no baseline score on file at all
    note = "No baseline score on file — defaulting to Intermediate. Consider completing the Baseline Assessment."
    return "intermediate", note


@app.post("/chat/start", response_model=StartResponse)
def start_session(
    session_id: str,
    topic: str = "",
    custom_topic: Optional[str] = None,
    level: Optional[str] = None,
):
    used_level, level_note = resolve_level(level)

    # ------------------------------------------------------------------
    # GAP-01: Custom / User-Defined Topic Input
    # ------------------------------------------------------------------
    if custom_topic is not None and custom_topic.strip():
        custom_topic = custom_topic.strip()

        # E-04: Empty Custom Topic Submission (backend guard; UI should already
        # disable Start under 3 chars, but never trust the client alone)
        if len(custom_topic) < 3:
            return StartResponse(
                status="rejected_too_short",
                topic=custom_topic,
                needs_clarification=True,
                reason="Please enter at least 3 characters.",
            )

        check = validate_custom_topic(custom_topic)

        # E-01: Inappropriate Custom Topic — reject before session starts
        if check["verdict"] == "UNSAFE":
            return StartResponse(
                status="rejected_unsafe",
                topic=custom_topic,
                reason="Please choose a different topic.",
            )

        # E-02: Topic Too Vague — ask a clarifying question, don't start yet
        if check["verdict"] == "VAGUE":
            return StartResponse(
                status="needs_clarification",
                topic=custom_topic,
                needs_clarification=True,
                reason=f"Could you tell me a bit more about \"{custom_topic}\"?",
            )

        # E-03: Topic Matches an Existing Preset — silently route into that flow
        if check["preset_match"] in TOPICS:
            matched_key = check["preset_match"]
            sessions[session_id] = {
                "topic": matched_key,
                "custom_topic": None,
                "history": [],
                "start_time": time.time(),
                "level": used_level,
                "level_adjusted": False,
            }
            return StartResponse(
                status="started",
                topic=TOPICS[matched_key],
                session_id=session_id,
                level=used_level,
                level_note=level_note,
            )

        # SAFE, no preset match -> genuine custom topic session
        sessions[session_id] = {
            "topic": "custom",
            "custom_topic": custom_topic,
            "history": [],
            "start_time": time.time(),
            "level": used_level,
            "level_adjusted": False,
        }

        custom_topics_log.append({
            "session_id": session_id,
            "topic": custom_topic,
            "ts": time.time(),
        })

        # AI opens with a tailored opening question (happy path step 4,
        # must land within ~3 seconds per acceptance criteria)
        system_msg = build_system_prompt("custom", custom_topic=custom_topic, level=used_level)
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": "Start the conversation."},
                ],
                timeout=10,
            )
            opening_reply = completion.choices[0].message.content
        except Exception:
            opening_reply = f"So, tell me a bit about {custom_topic} — what got you into it?"

        sessions[session_id]["history"].append({"role": "assistant", "content": opening_reply})

        return StartResponse(
            status="started",
            topic=custom_topic,
            session_id=session_id,
            opening_message=opening_reply,
            level=used_level,
            level_note=level_note,
        )

    # ------------------------------------------------------------------
    # Standard preset flow
    # ------------------------------------------------------------------
    sessions[session_id] = {
        "topic": topic,
        "custom_topic": None,
        "history": [],
        "start_time": time.time(),
        "level": used_level,
        "level_adjusted": False,
    }
    return StartResponse(
        status="started",
        topic=TOPICS.get(topic, topic),
        session_id=session_id,
        level=used_level,
        level_note=level_note,
    )


def run_chat_turn(session_id: str, topic: str, message: str) -> ChatResponse:
    # E-04: Empty Submission
    if not message or len(message.strip()) == 0:
        return ChatResponse(reply="Say something first — I'm listening!", session_duration_sec=0)

    session = sessions.get(session_id)
    if session is None:
        sessions[session_id] = {
            "topic": topic,
            "custom_topic": None,
            "history": [],
            "start_time": time.time(),
            "level": "intermediate",
            "level_adjusted": False,
        }
        session = sessions[session_id]

    # GAP-03: mid-session difficulty drift check. Rolling window of the user's
    # last 3 turns (including this one), judged by the LLM as a stand-in for
    # the real Confidence-Score engine. Allowed to fire at most once per
    # session (per acceptance criteria — no jarring repeated shifts) and
    # fails closed (no adjustment) on any judging error.
    level_adjustment_note = None
    if not session.get("level_adjusted", False):
        user_turns = [m["content"] for m in session["history"] if m["role"] == "user"]
        user_turns.append(message)
        if len(user_turns) >= 3:
            judged = judge_user_level(user_turns[-3:])
            if judged and judged != session.get("level"):
                session["level"] = judged
                session["level_adjusted"] = True
                level_adjustment_note = f"Difficulty adjusted to {judged.capitalize()} based on your recent responses."

    # Session is the source of truth for topic once /chat/start has run —
    # this matters for GAP-01 custom-topic sessions where `topic` == "custom".
    custom_topic = session.get("custom_topic")
    current_level = session.get("level", "intermediate")
    system_msg = build_system_prompt(
        session.get("topic", topic), custom_topic=custom_topic, level=current_level
    )

    messages = [{"role": "system", "content": system_msg}]
    messages += session["history"]
    messages.append({"role": "user", "content": message})

    status = "ok"
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            timeout=10,
        )
        reply = completion.choices[0].message.content
    except APITimeoutError:
        reply = "Connection slow, retrying..."
        status = "timeout"
    except Exception:
        reply = "Connection slow, retrying..."
        status = "error"

    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": reply})

    duration = time.time() - session["start_time"]

    key = (session_id, str(date.today()))
    running_total = daily_challenge.get(key, 0.0) + duration

    return ChatResponse(
        reply=reply,
        session_duration_sec=duration,
        status=status,
        daily_challenge_sec=running_total,
        level=current_level,
        level_adjustment_note=level_adjustment_note,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return run_chat_turn(req.session_id, req.topic, req.message)


@app.post("/chat/voice", response_model=ChatResponse)
async def chat_voice(session_id: str = Form(...), topic: str = Form(...), audio: UploadFile = File(...)):
    audio_bytes = await audio.read()

    # E-01: AI Transcription Failure
    if len(audio_bytes) == 0:
        return ChatResponse(
            reply="I didn't quite catch that, could you say it one more time?",
            session_duration_sec=0,
            status="transcription_failed",
        )

    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(audio.filename, audio_bytes),
        )
        text = transcript.text.strip()
    except Exception:
        return ChatResponse(
            reply="I didn't quite catch that, could you say it one more time?",
            session_duration_sec=0,
            status="transcription_failed",
        )

    if not text:
        return ChatResponse(
            reply="I didn't quite catch that, could you say it one more time?",
            session_duration_sec=0,
            status="transcription_failed",
        )

    return run_chat_turn(session_id, topic, text)


@app.post("/chat/end")
def end_session(session_id: str):
    session = sessions.pop(session_id, None)
    if session is None:
        return {"status": "no active session"}
    duration = time.time() - session["start_time"]

    key = (session_id, str(date.today()))
    daily_challenge[key] = daily_challenge.get(key, 0.0) + duration

    # GAP-02: archive the transcript before the live session is gone for good
    transcript_store[session_id] = {
        "topic": session.get("custom_topic") or session.get("topic"),
        "history": session["history"],
        "ended_at": time.time(),
        "level": session.get("level", "intermediate"),
        "level_adjusted": session.get("level_adjusted", False),
    }

    return {
        "status": "ended",
        "duration_sec": duration,
        "daily_challenge_total_sec": daily_challenge[key],
        # GAP-03 happy path step 5: feedback notes the level the session ran at
        "level": session.get("level", "intermediate"),
        "level_adjusted_mid_session": session.get("level_adjusted", False),
    }


class TranscriptTurn(BaseModel):
    index: int
    role: str
    content: str
    corrections: list = []   # stub — filled by NLP/Scoring engine, not this engine's job
    audio: Optional[str] = None  # stub — filled once audio storage exists (Speech-to-Text engineer)


class TranscriptResponse(BaseModel):
    status: str
    session_id: str
    topic: Optional[str] = None
    total_turns: int = 0
    offset: int = 0
    limit: int = 50
    turns: list[TranscriptTurn] = []
    note: Optional[str] = None


@app.get("/chat/transcript/{session_id}", response_model=TranscriptResponse)
def get_transcript(session_id: str, offset: int = 0, limit: int = 50):
    """GAP-02: Conversation Transcript Review & Replay.

    Reads from the archived store (post /chat/end) or, if the session is
    still live, from the active sessions dict — so a user can preview an
    in-progress transcript too. Grammar/vocabulary highlighting and audio
    playback are left as stubs for the NLP/Scoring and Speech-to-Text
    engineers respectively; this engine's job is just to expose the turns.
    """
    record = transcript_store.get(session_id)
    if record is not None:
        topic = record["topic"]
        history = record["history"]
    else:
        # E-04-style case: not archived yet — check if it's still an active session
        live = sessions.get(session_id)
        if live is None:
            return TranscriptResponse(
                status="not_found",
                session_id=session_id,
                note="No transcript found for this session.",
            )
        topic = live.get("custom_topic") or live.get("topic")
        history = live["history"]

    turns = [
        TranscriptTurn(index=i, role=msg["role"], content=msg["content"])
        for i, msg in enumerate(history)
    ]

    # E-03: paginate/lazy-load long transcripts rather than dumping everything
    paged = turns[offset: offset + limit]

    return TranscriptResponse(
        status="ok",
        session_id=session_id,
        topic=topic,
        total_turns=len(turns),
        offset=offset,
        limit=limit,
        turns=paged,
    )


# ---------------------------------------------------------------------------
# Interview Coach — job interview -> salary negotiation flow
# ---------------------------------------------------------------------------

interview_sessions = {}  # session_id -> {history, stage, exchange_count, start_time}

# transcript archive for interview sessions, same pattern as GAP-02 transcript_store —
# /interview/end pops interview_sessions, so archive here first for later review/replay.
interview_transcript_store = {}  # session_id -> {"role", "history", "final_stage", "ended_at"}


class InterviewRequest(BaseModel):
    session_id: str
    message: str
    role: str = "a professional role"  # e.g. "Software Engineer" — user-provided, no file parsing


class InterviewResponse(BaseModel):
    reply: str
    stage: str
    status: str = "ok"


@app.post("/interview/start")
def interview_start(session_id: str, role: str = "a professional role"):
    interview_sessions[session_id] = {
        "history": [],
        "stage": "job_interview",
        "exchange_count": 0,
        "role": role,
        "start_time": time.time(),
    }
    return {"status": "started", "stage": "job_interview", "role": role}


@app.post("/interview/chat", response_model=InterviewResponse)
def interview_chat(req: InterviewRequest):
    if not req.message or len(req.message.strip()) == 0:
        return InterviewResponse(reply="Take your time — go ahead when ready.", stage="job_interview")

    session = interview_sessions.get(req.session_id)
    if session is None:
        interview_sessions[req.session_id] = {
            "history": [],
            "stage": "job_interview",
            "exchange_count": 0,
            "role": req.role,
            "start_time": time.time(),
        }
        session = interview_sessions[req.session_id]

    system_msg = build_interview_prompt(session["stage"])
    # tell the model the target role being interviewed for
    system_msg = f"{system_msg}\n\nRole being interviewed for: {session['role']}."

    messages = [{"role": "system", "content": system_msg}]
    messages += session["history"]
    messages.append({"role": "user", "content": req.message})

    status = "ok"
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            timeout=10,
        )
        reply = completion.choices[0].message.content
    except APITimeoutError:
        reply = "Connection slow, retrying..."
        status = "timeout"
    except Exception:
        reply = "Connection slow, retrying..."
        status = "error"

    session["history"].append({"role": "user", "content": req.message})
    session["history"].append({"role": "assistant", "content": reply})

    # Stage transition: after enough exchanges in job_interview stage, flip to negotiation.
    if session["stage"] == "job_interview":
        session["exchange_count"] += 1
        if session["exchange_count"] >= 4:
            session["stage"] = "salary_negotiation"

    return InterviewResponse(reply=reply, stage=session["stage"], status=status)


@app.post("/interview/end")
def interview_end(session_id: str):
    session = interview_sessions.pop(session_id, None)
    if session is None:
        return {"status": "no active session"}
    duration = time.time() - session["start_time"]

    interview_transcript_store[session_id] = {
        "role": session.get("role"),
        "history": session["history"],
        "final_stage": session["stage"],
        "ended_at": time.time(),
    }

    return {"status": "ended", "duration_sec": duration, "final_stage": session["stage"]}


@app.get("/interview/transcript/{session_id}", response_model=TranscriptResponse)
def get_interview_transcript(session_id: str, offset: int = 0, limit: int = 50):
    """Interview Coach transcript review — same pattern as GAP-02's
    /chat/transcript. Reads from the archived store (post /interview/end) or,
    if the interview is still live, from the active interview_sessions dict.
    """
    record = interview_transcript_store.get(session_id)
    if record is not None:
        topic = record["role"]
        history = record["history"]
    else:
        live = interview_sessions.get(session_id)
        if live is None:
            return TranscriptResponse(
                status="not_found",
                session_id=session_id,
                note="No transcript found for this session.",
            )
        topic = live.get("role")
        history = live["history"]

    turns = [
        TranscriptTurn(index=i, role=msg["role"], content=msg["content"])
        for i, msg in enumerate(history)
    ]

    paged = turns[offset: offset + limit]

    return TranscriptResponse(
        status="ok",
        session_id=session_id,
        topic=topic,
        total_turns=len(turns),
        offset=offset,
        limit=limit,
        turns=paged,
    )