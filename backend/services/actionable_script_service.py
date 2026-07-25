import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi.responses import JSONResponse

from lib import confidence_engine, kv_store, llm_client, prompts, session_scorer
from services import coaching_service
from schemas.actionable_script_schemas import (
    BaselineScoresSchema,
    ProcessScriptRequest,
    ProcessScriptResponse,
    PronunciationHandoffRequest,
    SaveScriptRequest,
)

logger = logging.getLogger(__name__)

SAVED_SCRIPTS_NS = "saved_scripts"
MAX_SAVED_SCRIPTS_PER_USER = 500

CATEGORY_KEYWORDS = {
    "HR/Behavioral": [
        "weakness", "team", "conflict", "strength", "leadership", "challenge",
        "failure", "accomplishment", "manager", "colleague", "behavioral",
        "situation", "task", "action", "result", "hire", "workplace"
    ],
    "Technical": [
        "algorithm", "system design", "database", "code", "architecture", "api",
        "framework", "performance", "server", "data", "software", "backend",
        "frontend", "infrastructure", "bug", "deploy", "query", "optimiz"
    ],
    "Sales/Client": [
        "client", "deal", "revenue", "pitch", "negotiate", "customer",
        "contract", "sales", "account", "stakeholder", "closing"
    ],
    "Visa/Immigration": [
        "visa", "consul", "embassy", "immigration", "passport", "travel",
        "country", "stay", "officer", "interview"
    ],
}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "is", "was", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "it", "its", "that", "this", "these", "those", "by", "as", "from", "at",
    "we", "you", "i", "my", "me", "our", "us", "your", "they", "them",
    "their", "he", "him", "his", "she", "her", "will", "would", "can", "could",
    "should", "may", "might", "must", "shall", "not", "no", "so", "if", "but", "also"
}


def detect_category(text: str) -> str:
    """Map keywords in text to a category tag, defaulting to 'General'."""
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return category
    return "General"


def is_garbled_or_corrupted(text: str) -> bool:
    """Heuristic for corrupted or garbled text: low ratio of alphabetic chars to non-space length."""
    stripped = text.strip()
    non_space = re.sub(r"\s+", "", stripped)
    if len(non_space) <= 3:
        return False
    alpha_count = len(re.findall(r"[a-zA-Z]", non_space))
    return (alpha_count / len(non_space)) < 0.5


def extract_newly_introduced_words(original: str, rewrite: str) -> List[str]:
    """Find words newly introduced in rewrite for UI highlighting, excluding stop words."""
    if not rewrite:
        return []
    orig_words = set(re.findall(r"[a-zA-Z']+", original.lower()))
    rewrite_words = set(re.findall(r"[a-zA-Z']+", rewrite.lower()))
    new_words = rewrite_words - orig_words - STOP_WORDS
    return sorted([w for w in new_words if len(w) > 2])


def estimate_grammar_score(text: str) -> float:
    """Estimate a 0-100 grammar score for baseline assessment."""
    words = text.split()
    if not words:
        return 0.0
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 50.0
    pts = 100.0
    # Deduct for non-capitalized sentences
    cap_errors = sum(1 for s in sentences if not s[0].isupper())
    pts -= (cap_errors / len(sentences)) * 15.0
    # Deduct for slang / disfluency tokens
    lowered_words = [w.lower() for w in re.findall(r"[a-z']+", text)]
    slang_count = sum(1 for w in lowered_words if w in coaching_service._SLANG)
    pts -= min(35.0, slang_count * 10.0)
    return round(max(0.0, min(100.0, pts)), 2)


def calculate_baseline(text: str) -> BaselineScoresSchema:
    """Calculate the 7 baseline metrics permanently tied to the original submission."""
    vocab_score = session_scorer.estimate_vocabulary_score(text)
    
    # Confidence engine calculation
    scored_session = session_scorer.score_text_session(text)
    engine = confidence_engine.ConfidenceScoreEngine()
    conf_score = engine.calculate_session_confidence(scored_session.to_session_score())
    
    structure_score = session_scorer._written_fluency_score(text)
    grammar_score = estimate_grammar_score(text)
    
    offline_fb = coaching_service.offline_feedback("general_workplace", "", text, "text")
    tone_score = float(offline_fb["professional_tone"])
    clarity_score = float(offline_fb["clarity"])
    
    word_count = len(text.strip().split())
    if word_count >= 50:
        completeness_score = 95.0
    elif word_count >= 30:
        completeness_score = 85.0
    else:
        completeness_score = 70.0

    return BaselineScoresSchema(
        structure=structure_score,
        grammar=grammar_score,
        professional_tone=tone_score,
        vocabulary=vocab_score,
        confidence=conf_score,
        clarity=clarity_score,
        completeness=completeness_score,
    )


async def process_script(payload: ProcessScriptRequest):
    """Process a user submission: prechecks -> baseline assessment -> rewrite generation."""
    submission = (payload.submission or "").strip()
    script_id = uuid.uuid4().hex[:12]

    # 1) Rejection exception case: empty text
    if not submission:
        return JSONResponse(
            status_code=400,
            content={
                "error": "blank_submission",
                "message": "Submission text cannot be empty. Rewrite generation is disabled for empty input."
            }
        )

    # 2) Rejection exception case: non-English language specified
    requested_lang = (payload.language or "en").strip().lower()
    if requested_lang not in ("en", "english"):
        return JSONResponse(
            status_code=400,
            content={
                "error": "non_english",
                "message": "Please redo the exercise in English. Only English responses are supported."
            }
        )

    # 3) Rejection exception case: corrupted or garbled text
    if is_garbled_or_corrupted(submission):
        return JSONResponse(
            status_code=422,
            content={
                "error": "corrupted_text",
                "message": "Submitted text appears corrupted or garbled. Please retry with clear text."
            }
        )

    word_count = len(submission.split())

    # 4) Exception case: under 15 words -> mark baseline as Insufficient Data, skip rewrite
    if word_count < 15:
        return ProcessScriptResponse(
            script_id=script_id,
            baseline_status="Insufficient Data",
            baseline_scores=None,
            rewrite_status="skipped",
            polished_rewrite=None,
            rewrite_note="Insufficient data to generate rewrite (minimum 15 words required).",
            newly_introduced_words=[],
            category=detect_category(submission),
        )

    # PIECE 1: Baseline Quality Assessment (7 metrics, MUST be calculated BEFORE any rewrite)
    baseline_scores = calculate_baseline(submission)
    category = detect_category(submission)

    # PIECE 3: Check if original is already excellent (vocabulary, grammar, professional_tone all 85+)
    is_minor_polish = (
        baseline_scores.vocabulary >= 85.0
        and baseline_scores.grammar >= 85.0
        and baseline_scores.professional_tone >= 85.0
    )

    if is_minor_polish:
        rewrite_status = "minor_polish"
        default_note = "Excellent phrasing! Here is a slightly more concise alternative."
    else:
        rewrite_status = "success"
        default_note = None

    # LLM Rewrite Generation
    if not llm_client.is_configured():
        # Graceful degradation when no GROQ_API_KEY set
        return ProcessScriptResponse(
            script_id=script_id,
            baseline_status="completed",
            baseline_scores=baseline_scores,
            rewrite_status="failed",
            polished_rewrite=None,
            rewrite_note="LLM service is not configured (GROQ_API_KEY missing). Rewrite could not be generated.",
            newly_introduced_words=[],
            category=category,
        )

    prompt = prompts.build_actionable_script_rewrite_prompt(
        submission=submission,
        scenario_context=payload.scenario_context,
        is_minor_polish=is_minor_polish,
    )

    try:
        raw_reply = await llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        polished_rewrite = raw_reply.strip().strip('"')
        newly_words = extract_newly_introduced_words(submission, polished_rewrite)

        return ProcessScriptResponse(
            script_id=script_id,
            baseline_status="completed",
            baseline_scores=baseline_scores,
            rewrite_status=rewrite_status,
            polished_rewrite=polished_rewrite,
            rewrite_note=default_note,
            newly_introduced_words=newly_words,
            category=category,
        )
    except llm_client.LLMError as e:
        logger.warning("Actionable script rewrite generation failed: %s", e)
        return ProcessScriptResponse(
            script_id=script_id,
            baseline_status="completed",
            baseline_scores=baseline_scores,
            rewrite_status="failed",
            polished_rewrite=None,
            rewrite_note=f"LLM rewrite generation failed: {e}",
            newly_introduced_words=[],
            category=category,
        )


async def save_script(payload: SaveScriptRequest, user_id: str):
    """PIECE 2: Save a polished rewrite into the user's personal library (kv_store)."""
    # Validation: refuse to save if rewrite generation failed or was never generated
    if payload.rewrite_status == "failed" or not payload.polished_rewrite or not payload.polished_rewrite.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": "cannot_save_failed_script",
                "message": "A script whose rewrite generation failed, or was never successfully generated, cannot be saved."
            }
        )

    # Check 500 script cap per user
    all_values = await kv_store.store.list_values(SAVED_SCRIPTS_NS)
    user_scripts = [v for v in all_values if v.get("userId") == user_id or v.get("user_id") == user_id]
    
    if len(user_scripts) >= MAX_SAVED_SCRIPTS_PER_USER:
        return JSONResponse(
            status_code=400,
            content={
                "error": "library_full",
                "message": "Library full, delete an old script to save a new one."
            }
        )

    script_id = payload.script_id or uuid.uuid4().hex[:12]
    resolved_category = payload.category or detect_category(payload.original_text)

    record = {
        "script_id": script_id,
        "userId": user_id,
        "user_id": user_id,
        "original_text": payload.original_text,
        "polished_rewrite": payload.polished_rewrite,
        "category": resolved_category,
        "baseline_scores": payload.baseline_scores,
        "rewrite_status": payload.rewrite_status or "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    key = f"{user_id}:{script_id}"
    await kv_store.store.create(SAVED_SCRIPTS_NS, key, record)
    return {"status": "saved", "script": record}


async def list_user_scripts(user_id: str):
    """PIECE 2: List all saved scripts for the user."""
    all_values = await kv_store.store.list_values(SAVED_SCRIPTS_NS)
    user_scripts = [v for v in all_values if v.get("userId") == user_id or v.get("user_id") == user_id]
    return {"scripts": user_scripts, "total": len(user_scripts)}


async def delete_user_script(script_id: str, confirmed: bool, user_id: str):
    """PIECE 2: Delete a script with 2-step confirmation requirement."""
    key = f"{user_id}:{script_id}"
    existing = await kv_store.store.get(SAVED_SCRIPTS_NS, key)
    if not existing:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "Saved script not found in library."}
        )

    if not confirmed:
        return {
            "status": "pending_confirmation",
            "message": "Are you sure you want to delete this script?",
            "script_id": script_id,
            "confirmed_required": True
        }

    deleted = await kv_store.store.delete(SAVED_SCRIPTS_NS, key)
    return {"status": "deleted", "script_id": script_id, "success": deleted}


async def push_to_pronunciation(payload: PronunciationHandoffRequest, user_id: str):
    """
    PIECE 2: Push script to Pronunciation Coach.
    Handoff contract: If a Pronunciation Coach module does not exist yet,
    return the payload (polished text plus category) that such a module
    would eventually consume, with contract metadata.
    """
    return {
        "status": "handed_off",
        "contract": "pronunciation_coach_handoff_v1",
        "target_module": "PronunciationCoach",
        "payload": {
            "user_id": user_id,
            "script_id": payload.script_id,
            "polished_text": payload.polished_text,
            "category": payload.category,
        },
        "message": "Handoff payload ready for Pronunciation Coach module."
    }
