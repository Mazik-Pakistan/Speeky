"""
Scenario-Based Learning — SBL-US-01 .. SBL-US-11.

Persona-driven roleplay practice across 9 built-in real-world scenarios (restaurant,
airport, customer support, business meeting, doctor's appointment, apartment hunting,
public transportation, academic office hours, casual networking) plus admin-authored
custom scenarios (SBL-US-06).

Deliberately structured like coaching_service.py:
  * Pure, DB-free helpers (_classify_turn / _vocab_coverage / offline grading) hold the
    exception-handling rules and are unit-tested directly.
  * _roleplay_reply calls Groq (lib/llm_client) for in-character dialogue and grading,
    falling back to deterministic offline behaviour when Groq is unavailable.
  * The FastAPI controllers at the bottom are thin: gate access, persist ScenarioSession
    rows, and delegate to the helpers.

MVP scope note: text-only (no live mic capture exists anywhere in this app yet — see
plan doc); no code-switch detector; silence/rambling are approximated from message
length rather than real-time audio timers. See services.coaching_service for the
aggression phrase bank reused here.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends, Response
from fastapi.responses import JSONResponse
from prisma import Json

from lib import livekit_tokens, llm_client, prompts
from lib.prisma_client import db
from middlewares.auth_middleware import require_admin, require_auth
from schemas.scenario_schemas import (
    CustomScenarioSchema,
    ScenarioPreviewSchema,
    ScenarioTurnSchema,
    StartScenarioSchema,
)
from services.coaching_service import _AGGRESSIVE, _find_phrases

logger = logging.getLogger(__name__)

# Exception-handling thresholds
SILENCE_MIN_CHARS = 3        # shorter than this ⇒ treated as "didn't really answer"
RAMBLING_WORD_COUNT = 150    # longer than this ⇒ flagged as rambling
SILENCE_STREAK_LIMIT = 3     # 2 nudges, then the 3rd consecutive silent/idle turn auto-closes
AGGRESSION_STREAK_LIMIT = 2  # 1 warning, then the 2nd consecutive aggressive/cursing turn ends it

_EMERGENCY_PHRASES = [
    "heart attack", "can't breathe", "cannot breathe", "i'm dying", "im dying",
    "chest pain", "call an ambulance", "emergency", "suicidal", "kill myself",
]

# _AGGRESSIVE catches accusatory phrasing ("you failed", "unacceptable");
# it has no actual swear words, so cursing needs its own bank.
_PROFANITY = [
    "fuck", "fucking", "shit", "bullshit", "bitch", "asshole", "bastard", "damn you",
    "screw you", "piss off", "shut the hell up", "go to hell", "moron", "prick", "scumbag", "ass"
]

_POLITE_MARKERS = ["please", "could i", "could you", "would you mind", "thank you", "thanks"]
_RUDE_MARKERS = ["give me", "now.", "shut up", "whatever", "i don't care", "i dont care"]


def _is_medical_emergency(text: str) -> bool:
    lowered = f" {text.lower()} "
    return any(p in lowered for p in _EMERGENCY_PHRASES)


def _classify_turn(scenario_meta: Dict, message: str) -> str:
    """Generic exception classifier applied uniformly across all scenarios (mirrors
    interview_coach_service's answer classifier) rather than bespoke per-scenario code."""
    text = (message or "").strip()
    if scenario_meta.get("safety_mode") and _is_medical_emergency(text):
        return "emergency"
    if len(text) < SILENCE_MIN_CHARS:
        return "silence"
    lowered = f" {text.lower()} "
    if _find_phrases(lowered, _AGGRESSIVE) or _find_phrases(lowered, _PROFANITY):
        return "aggressive"
    if len(text.split()) > RAMBLING_WORD_COUNT:
        return "rambling"
    return "ok"


def _vocab_coverage(turns: List[Dict], target_vocab: List[str]) -> Dict[str, List[str]]:
    user_text = " ".join(t["content"] for t in turns if t.get("role") == "user").lower()
    used, missing = [], []
    for word in target_vocab:
        if word.lower() in user_text:
            used.append(word)
        else:
            missing.append(word)
    return {"used": used, "missing": missing}


def _offline_politeness(turns: List[Dict]) -> float:
    user_text = " ".join(t["content"] for t in turns if t.get("role") == "user").lower()
    score = 78.0
    for m in _POLITE_MARKERS:
        if m in user_text:
            score += 4.0
    for m in _RUDE_MARKERS:
        if m in user_text:
            score -= 12.0
    return round(max(0.0, min(100.0, score)), 2)


def _offline_tips(scenario_meta: Dict, turns: List[Dict], vocab_used: List[str], met_goal: bool) -> List[str]:
    """Deterministic 'tips' derivation from data already computed elsewhere — no LLM call,
    used both as the offline grader's tips and to backfill LLM tips that come back empty."""
    tips: List[str] = []
    missing = [w for w in scenario_meta.get("target_vocab", []) if w not in vocab_used]
    if missing:
        tips.append(f"Try working these words in next time: {', '.join(missing[:3])}.")
    politeness = _offline_politeness(turns)
    if politeness < 70:
        tips.append("Soften your phrasing — lead with \"Could I...\" or \"Would you mind...\" instead of blunt demands.")
    if scenario_meta.get("goal_type") == "negotiation" and not met_goal:
        tips.append("Don't accept the first answer — push back once more with a clear reason before settling.")
    if not tips:
        tips.append("Solid run — keep practicing to build consistency.")
    return tips[:3]


def offline_grade(scenario_meta: Dict, turns: List[Dict], vocab_used: List[str]) -> Dict:
    """Deterministic grader used when Groq isn't configured/reachable."""
    met_goal = True
    if scenario_meta.get("goal_type") == "negotiation":
        # Conservative heuristic: goal counted met only if the learner engaged in at
        # least a couple of back-and-forth turns (i.e. didn't just accept immediately).
        user_turns = [t for t in turns if t.get("role") == "user"]
        met_goal = len(user_turns) >= 2
    summary = (
        "Good engagement with the scenario."
        if vocab_used
        else "Try working more of the target vocabulary into your responses next time."
    )
    tips = _offline_tips(scenario_meta, turns, vocab_used, met_goal)
    return {
        "politeness": _offline_politeness(turns),
        "met_goal": met_goal,
        "summary": summary,
        "suggestion": tips[0],
        "tips": tips,
        # Rewriting prose convincingly needs an LLM — offline mode skips it rather than faking one.
        "original_line": "",
        "polished_line": "",
        "_source": "offline",
    }


async def grade_session(scenario_meta: Dict, turns: List[Dict], vocab_used: List[str]) -> Dict:
    if not llm_client.is_configured():
        return offline_grade(scenario_meta, turns, vocab_used)

    transcript = "\n".join(
        t["content"] for t in turns if t.get("role") == "user"
    )
    grading_prompt = prompts.build_scenario_grading_prompt(scenario_meta, transcript, vocab_used)
    try:
        raw = await llm_client.chat_json(
            [{"role": "user", "content": grading_prompt}], temperature=0.2, max_tokens=500
        )
        met_goal = bool(raw.get("met_goal", True))
        tips = [str(t).strip() for t in (raw.get("tips") or []) if str(t).strip()][:3]
        if not tips:
            tips = _offline_tips(scenario_meta, turns, vocab_used, met_goal)
        return {
            "politeness": max(0.0, min(100.0, float(raw.get("politeness", 0) or 0))),
            "met_goal": met_goal,
            "summary": raw.get("summary", ""),
            "suggestion": raw.get("suggestion", "") or tips[0],
            "tips": tips,
            "original_line": raw.get("original_line", "") or "",
            "polished_line": raw.get("polished_line", "") or "",
            "_source": "llm",
        }
    except (llm_client.LLMError, TypeError, ValueError) as e:
        logger.warning("Groq SBL grading failed (%s); using offline grader", e)
        return offline_grade(scenario_meta, turns, vocab_used)


# ── Scenario registry (built-in + admin custom) ────────────────────────────────
def _normalize_custom(row) -> Dict:
    return {
        "label": row.title,
        "category": row.category,
        "persona": row.persona,
        "intent": row.intent or row.systemPrompt[:160],
        "goal_type": row.goalType,
        "safety_mode": row.safetyMode,
        "corporate_tone": row.corporateTone,
        "target_vocab": row.targetVocab,
        "opening_fallback": row.openingLine or f"Let's begin — {row.title}.",
        "instructions": row.systemPrompt,
    }


async def list_scenarios() -> List[Dict]:
    custom_rows = await db.customscenario.find_many(order={"createdAt": "desc"})
    items = [
        {"key": key, **meta} for key, meta in prompts.SBL_SCENARIOS.items()
    ] + [
        {"key": f"custom:{row.id}", **_normalize_custom(row)} for row in custom_rows
    ]
    return [
        {
            "key": it["key"],
            "label": it["label"],
            "category": it["category"],
            "persona": it["persona"],
            "intent": it["intent"],
            "goal_type": it["goal_type"],
            "target_vocab": it["target_vocab"],
        }
        for it in items
    ]


async def scenario_meta(scenario_key: str) -> Optional[Dict]:
    if scenario_key.startswith("custom:"):
        row = await db.customscenario.find_unique(where={"id": scenario_key.split(":", 1)[1]})
        return _normalize_custom(row) if row else None
    return prompts.SBL_SCENARIOS.get(scenario_key)


# ═══════════════════════════════════════════════════════════════════════════════
# Roleplay dialogue (LLM with offline fallback) — mirrors coaching_service pattern
# ═══════════════════════════════════════════════════════════════════════════════
async def _roleplay_opening(scenario_key: str, meta: Dict) -> str:
    if not llm_client.is_configured():
        return meta["opening_fallback"]
    system = prompts.build_scenario_roleplay_prompt(meta)
    try:
        return await llm_client.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": "Begin the scene now with your first line."}],
            temperature=0.7, max_tokens=150,
        )
    except llm_client.LLMError:
        return meta["opening_fallback"]


_EMERGENCY_REPLY = (
    "I need to pause this practice session — what you're describing sounds like it could be "
    "a real medical emergency. Please contact real emergency services or a doctor right away. "
    "This session has been paused for your safety."
)

_SILENCE_AUTO_CLOSE_REPLY = (
    "It looks like you've stepped away, so I'll close this session here — your progress up to "
    "this point has been saved. Feel free to start a new scenario anytime."
)

_AGGRESSION_AUTO_CLOSE_REPLY = (
    "I did ask you to keep this respectful, and that hasn't happened, so I'm ending this practice "
    "session here. Your progress up to this point has been saved."
)


async def _roleplay_reply(meta: Dict, turns: List[Dict], classification: str) -> str:
    if classification == "emergency":
        return _EMERGENCY_REPLY
    if classification == "silence":
        return "Sorry, I didn't quite catch that — It looks like we may have lost you for a moment so whenever you're ready, go ahead and continue."

    if not llm_client.is_configured():
        if classification == "aggressive":
            return "That tone isn't necessary here — let's keep this respectful, please."
        if classification == "rambling":
            return "Okay — could you sum that up in a sentence or two?"
        return meta["opening_fallback"]

    system = prompts.build_scenario_roleplay_prompt(meta)
    if classification == "aggressive":
        # First/only warning — the caller (send_turn) decides when the streak limit is hit and
        # ends the session outright without calling this at all (see _AGGRESSION_AUTO_CLOSE_REPLY).
        system += ("\n\nThe user was rude, cursed, or aggressive. In character, react realistically: "
                   "show real displeasure and firmly ask them to be respectful, but don't end the "
                   "conversation yet — give them one more chance.")
    if classification == "rambling":
        system += "\n\nThe user's last message was long-winded. In character, politely ask them to summarize."
    messages = [{"role": "system", "content": system}] + [
        {"role": t["role"], "content": t["content"]} for t in turns
    ]
    try:
        return await llm_client.chat(messages, temperature=0.7, max_tokens=180)
    except llm_client.LLMError:
        return "Go on, I'm listening."


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI controllers
# ═══════════════════════════════════════════════════════════════════════════════
async def _require_access(user_id: str) -> Optional[JSONResponse]:
    from services.gating_service import GatedFeature, check_feature_access

    access = await check_feature_access(user_id, GatedFeature.SCENARIO_BASED_LEARNING.value)
    if not access["accessible"]:
        return JSONResponse(status_code=403, content={"error": access["reason"], "gating": access})
    return None


async def get_scenarios(user_id: str = Depends(require_auth)):
    return {"scenarios": await list_scenarios()}


# ── Voice mode: LiveKit room token (mirrors conversation_service._voice_token) ─
async def voice_token(session_id: str, user_id: str = Depends(require_auth)):
    gate = await _require_access(user_id)
    if gate:
        return gate
    session = await db.scenariosession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        return JSONResponse(status_code=404, content={"error": "Scenario session not found"})
    if not livekit_tokens.is_configured():
        return JSONResponse(status_code=503, content={
            "error": "Voice mode unavailable. Use text mode instead.",
        })
    return livekit_tokens.mint_room_token(session_id, identity=user_id)


async def get_scenario_detail(key: str, user_id: str = Depends(require_auth)):
    meta = await scenario_meta(key)
    if not meta:
        return JSONResponse(status_code=404, content={"error": "Unknown scenario"})
    return {"key": key, **meta}


async def start_session(payload: StartScenarioSchema, user_id: str = Depends(require_auth)):
    gate = await _require_access(user_id)
    if gate:
        return gate

    meta = await scenario_meta(payload.scenario_key)
    if not meta:
        return JSONResponse(status_code=400, content={"error": "Unknown scenario"})

    opening = await _roleplay_opening(payload.scenario_key, meta)
    session = await db.scenariosession.create(
        data={
            "userId": user_id,
            "scenarioKey": payload.scenario_key,
            "targetVocab": meta["target_vocab"],
            "turns": Json([{"role": "assistant", "content": opening}]),
        }
    )
    return {
        "session_id": session.id,
        "scenario_key": payload.scenario_key,
        "label": meta["label"],
        "persona": meta["persona"],
        "intent": meta["intent"],
        "target_vocab": meta["target_vocab"],
        "opening_message": opening,
    }


# Maps SBL's turn classifications onto session_memory_service.WEAKNESS_FLAGS' vocabulary —
# "emergency" and "ok" aren't weaknesses worth tracking across sessions, so they're omitted.
_WEAKNESS_FLAG_MAP = {"rambling": "rambling", "aggressive": "aggressive_tone", "silence": "prolonged_silence"}


async def _finalize_session(session_id: str, user_id: str, meta: Dict, target_vocab: List[str],
                            turns: List[Dict], status: str, flags: List[str]) -> Dict:
    """Grade + persist a session as done — shared by end_session (explicit) and
    send_turn's silence/aggression auto-close paths."""
    coverage = _vocab_coverage(turns, target_vocab)
    grade = await grade_session(meta, turns, coverage["used"])
    vocabulary_score = round(100 * len(coverage["used"]) / max(1, len(target_vocab)), 2)
    confidence = round((grade["politeness"] + vocabulary_score) / 2, 2)

    await db.scenariosession.update(
        where={"id": session_id},
        data={
            "turns": Json(turns),
            "status": status,
            "vocabUsed": coverage["used"],
            "politenessScore": grade["politeness"],
            "vocabularyScore": vocabulary_score,
            "confidenceScore": confidence,
            "metGoal": grade["met_goal"],
            "summary": grade["summary"],
            "tips": grade["tips"],
            "originalLine": grade["original_line"] or None,
            "polishedLine": grade["polished_line"] or None,
            "flags": Json(flags),
            "completedAt": datetime.now(timezone.utc),
        },
    )

    # Feed the generic cross-session memory profile (same shared infra conversation_service
    # uses) so recurring weak areas show up on the Profile page and in future personalized
    # openings, regardless of which feature the practice happened in.
    try:
        from services.session_memory_service import _record_session
        from schemas.session_memory_schemas import RecordSessionRequest

        await _record_session(user_id, RecordSessionRequest(
            session_id=session_id, session_type="scenario",
            flags_seen=flags, topic_or_mode=meta.get("label"),
            overall_score=int(round(confidence)),
        ))
    except Exception:
        pass  # best-effort — scenario scoring must not fail because memory logging did

    from services.vocabulary_progress_service import record_usage

    await record_usage(user_id, coverage["used"], coverage["missing"])

    return {
        "session_id": session_id,
        "status": status,
        "scores": {"politeness": grade["politeness"], "vocabulary": vocabulary_score, "confidence": confidence},
        "vocab_used": coverage["used"],
        "vocab_missing": coverage["missing"],
        "met_goal": grade["met_goal"] if meta.get("goal_type") == "negotiation" else None,
        "summary": grade["summary"],
        "suggestion": grade["suggestion"],
        "tips": grade["tips"],
        "original_line": grade["original_line"],
        "polished_line": grade["polished_line"],
        "graded_by": grade["_source"],
    }


async def send_turn(session_id: str, payload: ScenarioTurnSchema, user_id: str = Depends(require_auth)):
    session = await db.scenariosession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        return JSONResponse(status_code=404, content={"error": "Scenario session not found"})
    if session.status != "in_progress":
        return JSONResponse(status_code=400, content={"error": "Session is no longer active"})

    meta = await scenario_meta(session.scenarioKey)
    if not meta:
        return JSONResponse(status_code=400, content={"error": "Unknown scenario"})

    turns = list(session.turns) + [{"role": "user", "content": payload.message}]
    classification = _classify_turn(meta, payload.message)
    silence_streak = session.silenceStreak + 1 if classification == "silence" else 0
    aggression_streak = session.aggressionStreak + 1 if classification == "aggressive" else 0

    flags = list(session.flags)
    if classification in _WEAKNESS_FLAG_MAP:
        flags.append(_WEAKNESS_FLAG_MAP[classification])

    # (The frontend fires an empty turn after IDLE_TIMEOUT_SECONDS of inactivity, so this
    # also covers "stayed in the session but never spoke or typed", not just short replies.)
    if classification == "silence" and silence_streak >= SILENCE_STREAK_LIMIT:
        turns.append({"role": "assistant", "content": _SILENCE_AUTO_CLOSE_REPLY})
        await _finalize_session(session_id, user_id, meta, session.targetVocab, turns, "completed", flags)
        return {
            "session_id": session_id,
            "reply": _SILENCE_AUTO_CLOSE_REPLY,
            "status": "completed",
            "classification": "silence",
        }

    # One warning for aggression/cursing, then the scenario ends on the next offense —
    # graduated, matching how a real person would react, not an instant kill on turn one.
    if classification == "aggressive" and aggression_streak >= AGGRESSION_STREAK_LIMIT:
        turns.append({"role": "assistant", "content": _AGGRESSION_AUTO_CLOSE_REPLY})
        await _finalize_session(session_id, user_id, meta, session.targetVocab, turns, "ended_early", flags)
        return {
            "session_id": session_id,
            "reply": _AGGRESSION_AUTO_CLOSE_REPLY,
            "status": "ended_early",
            "classification": "aggressive",
        }

    reply = await _roleplay_reply(meta, turns, classification)
    turns.append({"role": "assistant", "content": reply})

    new_status = "ended_early" if classification == "emergency" else "in_progress"

    await db.scenariosession.update(
        where={"id": session_id},
        data={
            "turns": Json(turns), "status": new_status,
            "silenceStreak": silence_streak, "aggressionStreak": aggression_streak,
            "flags": Json(flags),
        },
    )
    return {
        "session_id": session_id,
        "reply": reply,
        "status": new_status,
        "classification": classification,
    }


async def end_session(session_id: str, user_id: str = Depends(require_auth)):
    session = await db.scenariosession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        return JSONResponse(status_code=404, content={"error": "Scenario session not found"})
    if session.completedAt:
        return JSONResponse(status_code=400, content={"error": "Session already completed"})

    meta = await scenario_meta(session.scenarioKey)
    final_status = session.status if session.status == "ended_early" else "completed"
    return await _finalize_session(
        session_id, user_id, meta, session.targetVocab, list(session.turns), final_status, list(session.flags)
    )


async def get_session(session_id: str, user_id: str = Depends(require_auth)):
    session = await db.scenariosession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        return JSONResponse(status_code=404, content={"error": "Scenario session not found"})
    return {
        "session_id": session.id,
        "scenario_key": session.scenarioKey,
        "status": session.status,
        "turns": session.turns,
        "target_vocab": session.targetVocab,
        "vocab_used": session.vocabUsed,
        "scores": {
            "politeness": session.politenessScore,
            "vocabulary": session.vocabularyScore,
            "confidence": session.confidenceScore,
        },
        "met_goal": session.metGoal,
        "summary": session.summary,
        "tips": session.tips,
        "original_line": session.originalLine,
        "polished_line": session.polishedLine,
        "completed_at": session.completedAt.isoformat() if session.completedAt else None,
    }


# ── Admin: custom scenario CRUD (SBL-US-06) ────────────────────────────────────
def _serialize_custom(row) -> Dict:
    return {
        "id": row.id,
        "title": row.title,
        "category": row.category,
        "persona": row.persona,
        "intent": row.intent,
        "system_prompt": row.systemPrompt,
        "opening_line": row.openingLine,
        "target_vocab": row.targetVocab,
        "goal_type": row.goalType,
        "safety_mode": row.safetyMode,
        "corporate_tone": row.corporateTone,
        "created_at": row.createdAt.isoformat(),
        "updated_at": row.updatedAt.isoformat(),
    }


async def admin_list_custom(user_id: str = Depends(require_admin)):
    rows = await db.customscenario.find_many(order={"createdAt": "desc"})
    return {"scenarios": [_serialize_custom(r) for r in rows]}


async def admin_create_custom(payload: CustomScenarioSchema, user_id: str = Depends(require_admin)):
    existing = await db.customscenario.find_unique(where={"title": payload.title})
    if existing:
        return JSONResponse(status_code=409, content={"error": "A scenario with this title already exists"})
    row = await db.customscenario.create(
        data={
            "title": payload.title,
            "category": payload.category,
            "persona": payload.persona,
            "intent": payload.intent,
            "systemPrompt": payload.system_prompt,
            "openingLine": payload.opening_line,
            "targetVocab": payload.target_vocab,
            "goalType": payload.goal_type,
            "safetyMode": payload.safety_mode,
            "corporateTone": payload.corporate_tone,
        }
    )
    return _serialize_custom(row)


async def admin_update_custom(scenario_id: str, payload: CustomScenarioSchema, user_id: str = Depends(require_admin)):
    row = await db.customscenario.find_unique(where={"id": scenario_id})
    if not row:
        return JSONResponse(status_code=404, content={"error": "Custom scenario not found"})
    collision = await db.customscenario.find_unique(where={"title": payload.title})
    if collision and collision.id != scenario_id:
        return JSONResponse(status_code=409, content={"error": "A scenario with this title already exists"})
    updated = await db.customscenario.update(
        where={"id": scenario_id},
        data={
            "title": payload.title,
            "category": payload.category,
            "persona": payload.persona,
            "intent": payload.intent,
            "systemPrompt": payload.system_prompt,
            "openingLine": payload.opening_line,
            "targetVocab": payload.target_vocab,
            "goalType": payload.goal_type,
            "safetyMode": payload.safety_mode,
            "corporateTone": payload.corporate_tone,
        },
    )
    return _serialize_custom(updated)


async def admin_preview_custom(payload: ScenarioPreviewSchema, user_id: str = Depends(require_admin)):
    meta = {
        "label": "Preview",
        "persona": payload.persona,
        "intent": "",
        "goal_type": payload.goal_type,
        "safety_mode": payload.safety_mode,
        "corporate_tone": payload.corporate_tone,
        "target_vocab": payload.target_vocab or ["(none set)"],
        "opening_fallback": payload.opening_line or f"Let's begin — {payload.persona}.",
        "instructions": payload.system_prompt,
    }
    turns = [t.model_dump() for t in payload.turns]

    if not payload.message:
        opening = await _roleplay_opening("preview", meta)
        return {"reply": opening, "classification": "ok"}

    turns.append({"role": "user", "content": payload.message})
    classification = _classify_turn(meta, payload.message)
    reply = await _roleplay_reply(meta, turns, classification)
    return {"reply": reply, "classification": classification}


async def admin_delete_custom(scenario_id: str, user_id: str = Depends(require_admin)):
    row = await db.customscenario.find_unique(where={"id": scenario_id})
    if not row:
        return JSONResponse(status_code=404, content={"error": "Custom scenario not found"})
    await db.customscenario.delete(where={"id": scenario_id})
    return Response(status_code=204)
