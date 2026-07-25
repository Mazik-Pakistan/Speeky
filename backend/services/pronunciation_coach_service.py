"""
Pronunciation Coach (GAP-03 / GAP-04 / GAP-05, US-71/72/73), the Retry Loop Mechanic
(US-071 / US-78), and Session Interruption Recovery (GAP-09) — one continuous session
flow: practice a phoneme-targeted sentence, retry specific words, resume if interrupted.

Session state is a nested dict persisted as one KvEntry blob (lib.kv_store), same
approach as interview_coach_service. Real audio scoring is NOT a stand-in here: attempt
and retry submissions take a raw audio upload and run it through lib/recording_engine.py
(STT + VAD + prosody), the same pipeline services/accent_assessment_service.py uses —
word correctness comes from lib/recording_engine.classify_word_status, not a text diff.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from lib import kv_store, recording_engine, text_alignment
from lib.audio_io import AudioDecodeError
from lib.prompts import (
    CODE_SWITCH_PARTIAL_OVERLAP_CEILING,
    DEFAULT_SENTENCE_SET,
    EXTENDED_ABSENCE_HOURS,
    INTERRUPTION_MESSAGES,
    MAX_CONSECUTIVE_OFFSCRIPT_ATTEMPTS,
    MAX_CONSECUTIVE_SAME_PHONEME,
    MAX_CONSECUTIVE_SILENT_ATTEMPTS,
    OFF_SCRIPT_PHONEME_OVERLAP_THRESHOLD,
    PRONUNCIATION_MESSAGES,
    RETRY_FRUSTRATION_THRESHOLD,
    RETRY_MESSAGES,
    SENTENCE_BANK,
    build_phoneme_tag,
    build_retry_diff_message,
)
from lib.recording_engine import RejectionReason
from lib.speech_config import load_speech_config
from lib.text_alignment import WordStatus
from middlewares.auth_middleware import require_auth
from schemas.pronunciation_schemas import DeviceScopedRequest, StartSessionRequest
from utils.feature_errors import (
    InvalidSubmissionError,
    SessionAlreadyEndedError,
    SessionNotFoundError,
    UnreadableAudioError,
    UploadTooLargeError,
)

NAMESPACE = "pronunciation_sessions"
PHONEME_ORDER = list(SENTENCE_BANK.keys())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return f"pron_{uuid.uuid4().hex[:12]}"


def _tokens(text: str) -> List[str]:
    return [w for w in re.sub(r"[^\w\s]", "", text.lower()).split() if w]


def _has_non_english_word(text: str) -> bool:
    """Stand-in code-switch detector: any word containing non-ASCII letters (no real
    language-ID model here — orthogonal to the STT/alignment pipeline, which only
    tells us WHAT was said, not WHICH language it's in)."""
    return any(any(ord(ch) > 127 for ch in tok) for tok in _tokens(text))


def _analyze_upload(audio_bytes: bytes, config, initial_prompt: Optional[str] = None) -> recording_engine.RecordingAnalysis:
    max_bytes = config.pronunciation_max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise UploadTooLargeError(f"Recording exceeds the {config.pronunciation_max_upload_mb}MB limit")
    try:
        return recording_engine.analyze_recording(audio_bytes, config, initial_prompt=initial_prompt)
    except AudioDecodeError as e:
        raise UnreadableAudioError(str(e))


def _coverage_ratio(analysis: recording_engine.RecordingAnalysis, target_text: str) -> float:
    """Real matched-word ratio for off-script/code-switch gating. Deliberately NOT the
    same "matched" count lib/text_alignment.compute_passage_coverage uses (that counts
    difflib "replace" pairs as matched too, since passage coverage just wants to know
    how much was ATTEMPTED). Here we need real content overlap: a "replace" pair means
    some transcript word occupies that slot but ISN'T the target word — an unrelated
    transcript aligns nearly every slot that way, so counting it as "matched" would make
    off-script detection nearly impossible to trigger."""
    aligned = recording_engine.align_to_sentence(analysis, target_text)
    if not aligned:
        return 1.0
    matched = sum(
        1 for a in aligned
        if a.transcript_word is not None and text_alignment.normalize(a.transcript_word) == text_alignment.normalize(a.target_word)
    )
    return matched / len(aligned)


def _score_words(analysis: recording_engine.RecordingAnalysis, target_text: str, config) -> List[Dict]:
    """Real per-word correct/incorrect via the shared recording_engine classifier
    (same one services/accent_assessment_service.py uses) — MISPRONOUNCED, STRESS_ERROR,
    and SKIPPED all collapse to `correct=False` here, matching the boolean granularity
    the existing session-flow (phoneme rotation, response shape) already expects."""
    aligned = recording_engine.align_to_sentence(analysis, target_text)
    words = []
    for a in aligned:
        timing = analysis.words[a.transcript_index] if a.transcript_index is not None else None
        status = recording_engine.classify_word_status(a.target_word, timing, analysis.prosody, config)
        words.append({"word": a.target_word, "correct": status == WordStatus.CORRECT})
    return words


def _next_sentence(session: dict, phoneme: str) -> str:
    seen = session["seen_sentences"].setdefault(phoneme, [])
    bank = SENTENCE_BANK.get(phoneme, DEFAULT_SENTENCE_SET)
    remaining = [s for s in bank if s not in seen]
    if remaining:
        sentence = remaining[0]
        seen.append(sentence)
        return sentence
    # GAP-03: bank exhausted for this phoneme — reuse, flagged via content_gap_flagged.
    sentence = bank[len(seen) % len(bank)]
    seen.append(sentence)
    return sentence


def _advance(session: dict, had_error: bool) -> None:
    """GAP-03 E-03: stick with a phoneme the user is getting wrong, but cap consecutive
    repeats so they aren't stuck forever on one sound."""
    if had_error and session["phoneme_streak"] < MAX_CONSECUTIVE_SAME_PHONEME:
        session["phoneme_streak"] += 1
    else:
        current_index = PHONEME_ORDER.index(session["current_phoneme"])
        session["current_phoneme"] = PHONEME_ORDER[(current_index + 1) % len(PHONEME_ORDER)]
        session["phoneme_streak"] = 1
    session["current_sentence"] = _next_sentence(session, session["current_phoneme"])


async def _get_session(session_id: str, user_id: str) -> dict:
    session = await kv_store.store.get(NAMESPACE, session_id)
    if session is None or session.get("user_id") != user_id:
        raise SessionNotFoundError(f"Session {session_id} not found")
    return session


def _record_attempt(session: dict, message_key: str, words: List[Dict]) -> None:
    session["attempts"].append({
        "phoneme": session["current_phoneme"],
        "sentence": session["current_sentence"],
        "message_key": message_key,
        "words": words,
        "created_at": _now(),
    })
    session["last_completed"] = {
        "phoneme": session["current_phoneme"],
        "sentence": session["current_sentence"],
        "words": {w["word"]: w["correct"] for w in words},
    }


# ── entry service functions ───────────────────────────────────────────────────
async def _start_session(user_id: str, device_id: str) -> dict:
    now = _now()
    # GAP-09: a fresh start supersedes any session this user still has open elsewhere —
    # what makes conflict_second_device meaningful if the old device tries to resume it.
    existing = await kv_store.store.list_values(NAMESPACE)
    for other in existing:
        if other["user_id"] == user_id and other["status"] != "completed" and not other.get("superseded"):
            other["superseded"] = True
            other["superseded_by_device_id"] = device_id
            await kv_store.store.update(NAMESPACE, other["session_id"], other)

    session_id = _new_id()
    phoneme = PHONEME_ORDER[0]
    session = {
        "session_id": session_id, "user_id": user_id, "status": "active",
        "current_phoneme": phoneme, "current_sentence": DEFAULT_SENTENCE_SET[0],
        "phoneme_streak": 1, "seen_sentences": {},
        "consecutive_silent": 0, "consecutive_offscript": 0,
        "attempts": [], "last_completed": None,
        "active_device_id": device_id, "last_active_at": now,
        "superseded": False, "superseded_by_device_id": None,
        "started_at": now, "ended_at": None,
    }
    await kv_store.store.create(NAMESPACE, session_id, session)
    return session


async def _submit_attempt(user_id: str, session_id: str, audio_bytes: bytes) -> dict:
    session = await _get_session(session_id, user_id)
    if session["status"] == "completed":
        raise SessionAlreadyEndedError("Cannot submit an attempt to a completed session")

    config = load_speech_config()
    sentence = session["current_sentence"]
    # initial_prompt biases STT toward the sentence the user was asked to read — see
    # lib/stt_engine.transcribe's docstring for why this materially helps accuracy.
    analysis = _analyze_upload(audio_bytes, config, initial_prompt=sentence)

    session["last_active_at"] = _now()
    transcript = analysis.transcript or ""

    # GAP-04: silence / volume gating, before any content scoring — real, driven by
    # recording_engine.analyze_recording's VAD + dBFS/SNR rejection classification.
    if analysis.rejection == RejectionReason.NO_SPEECH_DETECTED:
        session["consecutive_silent"] += 1
        key = (
            "mic_troubleshoot"
            if session["consecutive_silent"] >= MAX_CONSECUTIVE_SILENT_ATTEMPTS
            else "no_speech_detected"
        )
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {"session_id": session_id, "message_key": key, "message": PRONUNCIATION_MESSAGES[key], "words": [], "transcript": transcript}

    if analysis.rejection in (RejectionReason.AUDIO_TOO_QUIET, RejectionReason.BACKGROUND_NOISE_TOO_HIGH):
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {
            "session_id": session_id, "message_key": "too_quiet",
            "message": PRONUNCIATION_MESSAGES["too_quiet"], "words": [], "transcript": transcript,
        }

    session["consecutive_silent"] = 0

    # GAP-05: off-script / code-switch detection, via real alignment coverage against
    # the full target sentence (lib/text_alignment.align_words under the hood).
    coverage = _coverage_ratio(analysis, sentence)
    if coverage < OFF_SCRIPT_PHONEME_OVERLAP_THRESHOLD:
        session["consecutive_offscript"] += 1
        key = (
            "off_script_repeated"
            if session["consecutive_offscript"] >= MAX_CONSECUTIVE_OFFSCRIPT_ATTEMPTS
            else "off_script"
        )
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {"session_id": session_id, "message_key": key, "message": PRONUNCIATION_MESSAGES[key], "words": [], "transcript": transcript}

    session["consecutive_offscript"] = 0
    sentence_word_count = len(_tokens(sentence))
    transcript_word_count = len(_tokens(transcript))
    # Only the portion of the sentence actually attempted gets scored — mirrors the
    # target sentence down to however many words came through, so an honestly partial/
    # code-switched attempt isn't penalized for words never reached.
    attempted_sentence = " ".join(sentence.split()[:transcript_word_count]) or sentence

    # A non-English word mixed into an otherwise on-script attempt -> code-switch, not a
    # plain mispronunciation. (A single wrong English word just gets marked incorrect below.)
    # Never a clean full read, so it never advances — same sentence again, whole thing.
    if _has_non_english_word(transcript) and coverage < CODE_SWITCH_PARTIAL_OVERLAP_CEILING:
        words = _score_words(analysis, attempted_sentence, config)
        _record_attempt(session, "code_switch_partial", words)
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {
            "session_id": session_id, "message_key": "code_switch_partial",
            "message": PRONUNCIATION_MESSAGES["code_switch_partial"], "words": words, "transcript": transcript,
        }

    # Cut off mid-sentence but what came through was on-script: mark scored words only.
    # Incomplete either way, so it never advances — same sentence again, whole thing.
    if transcript_word_count < sentence_word_count * 0.6:
        words = _score_words(analysis, attempted_sentence, config)
        _record_attempt(session, "partial_muted", words)
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {
            "session_id": session_id, "message_key": "partial_muted",
            "message": PRONUNCIATION_MESSAGES["partial_muted"], "words": words, "transcript": transcript,
        }

    # Only a fully correct read of the whole sentence advances. Any word wrong -> same
    # sentence again in full, no per-word retry — _advance (phoneme rotation, new
    # sentence) only runs on a clean pass.
    words = _score_words(analysis, sentence, config)
    had_error = any(not w["correct"] for w in words)
    message_key = "needs_retry" if had_error else "scored_ok"
    _record_attempt(session, message_key, words)
    if had_error:
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {
            "session_id": session_id, "message_key": "needs_retry",
            "message": PRONUNCIATION_MESSAGES["needs_retry"], "words": words, "transcript": transcript,
        }

    _advance(session, False)
    await kv_store.store.update(NAMESPACE, session_id, session)
    return {
        "session_id": session_id, "message_key": "scored_ok",
        "message": PRONUNCIATION_MESSAGES["scored_ok"], "words": words, "transcript": transcript,
        "next_sentence": session["current_sentence"], "next_phoneme": session["current_phoneme"],
        "next_phoneme_tag": build_phoneme_tag(session["current_phoneme"]),
    }


async def _retry_word(user_id: str, session_id: str, target_word: str, audio_bytes: bytes) -> dict:
    session = await _get_session(session_id, user_id)
    last = session.get("last_completed")
    target = target_word.lower().strip()
    if last is None or target not in last["words"]:
        raise InvalidSubmissionError(f"'{target_word}' is not part of the last completed attempt")

    config = load_speech_config()
    # initial_prompt biases STT toward the single word being retried — isolated
    # single-word clips have the least context of any audio this pipeline handles, so
    # this is where prompt-biasing helps recognition accuracy the most.
    analysis = _analyze_upload(audio_bytes, config, initial_prompt=target)
    session["last_active_at"] = _now()

    # E-03: empty/too-short audio is rejected outright — real recording duration/VAD,
    # not a client-supplied guess, and it never touches the frustration counter below.
    if analysis.duration_seconds < config.min_recording_seconds or not analysis.vad.has_speech:
        await kv_store.store.update(NAMESPACE, session_id, session)
        return {
            "session_id": session_id, "message": RETRY_MESSAGES["empty_audio"],
            "frustration_breakdown": False, "transcript": analysis.transcript or "",
        }

    aligned = recording_engine.align_to_sentence(analysis, target)
    timing = None
    if aligned and aligned[0].transcript_index is not None:
        timing = analysis.words[aligned[0].transcript_index]
    status = recording_engine.classify_word_status(target, timing, analysis.prosody, config)
    new_correct = status == WordStatus.CORRECT

    was_correct = last["words"][target]
    last["words"][target] = new_correct

    fail_counts = session.setdefault("retry_fail_counts", {})
    if new_correct:
        fail_counts[target] = 0
    else:
        fail_counts[target] = fail_counts.get(target, 0) + 1

    frustration = fail_counts[target] >= RETRY_FRUSTRATION_THRESHOLD
    if frustration:
        message = RETRY_MESSAGES["frustration_breakdown"]
    else:
        fixed_word = target if (new_correct and not was_correct) else None
        broken_word = target if not new_correct else None
        message = build_retry_diff_message(fixed_word, broken_word)

    await kv_store.store.update(NAMESPACE, session_id, session)
    return {
        "session_id": session_id, "message": message, "frustration_breakdown": frustration,
        "transcript": analysis.transcript or "",
    }


async def _interrupt_session(user_id: str, session_id: str) -> dict:
    session = await _get_session(session_id, user_id)
    if session["status"] == "completed":
        raise SessionAlreadyEndedError("Cannot interrupt a completed session")
    session["status"] = "interrupted"
    session["last_active_at"] = _now()
    await kv_store.store.update(NAMESPACE, session_id, session)
    return {"session_id": session_id, "status": session["status"], "message": INTERRUPTION_MESSAGES["discard_in_flight"]}


async def _find_resumable_session(user_id: str) -> dict:
    sessions = [
        s for s in await kv_store.store.list_values(NAMESPACE)
        if s["user_id"] == user_id and s["status"] != "completed"
    ]
    if not sessions:
        return {"found": False, "message": INTERRUPTION_MESSAGES["not_found"]}
    latest = max(sessions, key=lambda s: s["last_active_at"])
    stale = _now() - latest["last_active_at"] > timedelta(hours=EXTENDED_ABSENCE_HOURS)
    message = INTERRUPTION_MESSAGES["stale_resume_prompt"] if stale else INTERRUPTION_MESSAGES["resume_prompt"]
    return {"found": True, "session_id": latest["session_id"], "message": message, "stale": stale}


async def _resume_session(user_id: str, session_id: str, device_id: str) -> dict:
    session = await _get_session(session_id, user_id)
    if session["status"] == "completed":
        raise SessionAlreadyEndedError("Cannot resume a completed session")
    if session.get("superseded") and session.get("superseded_by_device_id") != device_id:
        raise InvalidSubmissionError(INTERRUPTION_MESSAGES["conflict_second_device"])

    stale = _now() - session["last_active_at"] > timedelta(hours=EXTENDED_ABSENCE_HOURS)
    session["status"] = "active"
    session["active_device_id"] = device_id
    session["last_active_at"] = _now()
    await kv_store.store.update(NAMESPACE, session_id, session)
    message = INTERRUPTION_MESSAGES["stale_resume_prompt"] if stale else INTERRUPTION_MESSAGES["resume_prompt"]
    return {
        "session_id": session_id, "status": session["status"],
        "phoneme": session["current_phoneme"], "phoneme_tag": build_phoneme_tag(session["current_phoneme"]),
        "sentence": session["current_sentence"], "message": message,
    }


async def _end_session(user_id: str, session_id: str) -> dict:
    session = await _get_session(session_id, user_id)
    if session["status"] != "completed":
        session["status"] = "completed"
        session["ended_at"] = _now()
        await kv_store.store.update(NAMESPACE, session_id, session)

    by_phoneme: Dict[str, Dict] = {}
    for attempt in session["attempts"]:
        entry = by_phoneme.setdefault(attempt["phoneme"], {"attempts": 0, "correct_words": 0, "total_words": 0})
        entry["attempts"] += 1
        entry["total_words"] += len(attempt["words"])
        entry["correct_words"] += sum(1 for w in attempt["words"] if w["correct"])

    return {
        "session_id": session_id, "status": session["status"],
        "attempt_count": len(session["attempts"]),
        "phoneme_accuracy": [
            {"phoneme": phoneme, **stats} for phoneme, stats in by_phoneme.items()
        ],
        "ended_at": session["ended_at"],
    }


async def _get_session_snapshot(user_id: str, session_id: str) -> dict:
    session = await _get_session(session_id, user_id)
    return {
        "session_id": session_id, "status": session["status"],
        "phoneme": session["current_phoneme"], "phoneme_tag": build_phoneme_tag(session["current_phoneme"]),
        "sentence": session["current_sentence"],
    }


# ── controllers (auth-gated) ──────────────────────────────────────────────────
async def _require_access(user_id: str) -> Optional[JSONResponse]:
    """Gate Pronunciation Coach behind a completed baseline assessment, same gate/shape
    as coaching_service._require_access."""
    from services.gating_service import GatedFeature, check_feature_access

    access = await check_feature_access(user_id, GatedFeature.SCENARIO_BASED_LEARNING.value)
    if not access["accessible"]:
        return JSONResponse(status_code=403, content={"error": access["reason"], "gating": access})
    return None


async def start_session(payload: StartSessionRequest, user_id: str = Depends(require_auth)):
    gate = await _require_access(user_id)
    if gate:
        return gate
    session = await _start_session(user_id, payload.device_id)
    # Shape to SessionStartResponse: _start_session returns the internal session dict
    # (current_phoneme/current_sentence, plus fields that aren't the client's business),
    # not the wire response — this mapping is what the frontend's `sentence`/
    # `phoneme`/`phoneme_tag` fields actually come from.
    return {
        "session_id": session["session_id"],
        "status": session["status"],
        "phoneme": session["current_phoneme"],
        "phoneme_tag": build_phoneme_tag(session["current_phoneme"]),
        "sentence": session["current_sentence"],
        "message": None,
        "started_at": session["started_at"],
    }


async def submit_attempt(session_id: str, audio: UploadFile = File(...), user_id: str = Depends(require_auth)):
    audio_bytes = await audio.read()
    return await _submit_attempt(user_id, session_id, audio_bytes)


async def retry_word(
    session_id: str,
    target_word: str = Form(...),
    audio: UploadFile = File(...),
    user_id: str = Depends(require_auth),
):
    audio_bytes = await audio.read()
    return await _retry_word(user_id, session_id, target_word, audio_bytes)


async def interrupt_session(session_id: str, user_id: str = Depends(require_auth)):
    return await _interrupt_session(user_id, session_id)


async def check_resumable_session(user_id: str = Depends(require_auth)):
    return await _find_resumable_session(user_id)


async def resume_session(session_id: str, payload: DeviceScopedRequest, user_id: str = Depends(require_auth)):
    return await _resume_session(user_id, session_id, payload.device_id)


async def end_session(session_id: str, user_id: str = Depends(require_auth)):
    return await _end_session(user_id, session_id)


async def get_session(session_id: str, user_id: str = Depends(require_auth)):
    return await _get_session_snapshot(user_id, session_id)
