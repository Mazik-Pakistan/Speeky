"""
Pronunciation Coach (US-95): read-a-sentence-aloud, get word-level pronunciation
feedback. Built entirely on top of lib/recording_engine.py (Story #1) — this module
adds only the word-status classification, scoring, and persistence that are specific
to this feature.
"""

import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from prisma import Json

from lib import prosody_engine, recording_engine, text_alignment
from lib.audio_io import AudioDecodeError
from lib.prisma_client import db
from lib.recording_engine import RejectionReason
from lib.speech_config import load_speech_config
from lib.text_alignment import WordStatus
from middlewares.auth_middleware import require_auth
from schemas.pronunciation_schemas import (
    PronunciationResultSchema,
    RecordingRejectedSchema,
    TargetSentenceSchema,
    WordResultSchema,
)
from utils.feature_errors import SentenceNotFoundError, UnreadableAudioError, UploadTooLargeError

logger = logging.getLogger(__name__)

_STATUS_POINTS = {
    WordStatus.CORRECT: 100.0,
    WordStatus.STRESS_ERROR: 70.0,
    WordStatus.MISPRONOUNCED: 30.0,
    WordStatus.SKIPPED: 0.0,
}


class SentenceBank:
    def __init__(self):
        path = Path(__file__).parent.parent / "data" / "pronunciation_sentences.json"
        with open(path, "r", encoding="utf-8") as f:
            raw: Dict[str, List[dict]] = json.load(f)
        self._by_id = {s["sentence_id"]: s for sentences in raw.values() for s in sentences}
        self._all = list(self._by_id.values())

    def get_by_id(self, sentence_id: str) -> Optional[dict]:
        return self._by_id.get(sentence_id)

    def all(self) -> List[dict]:
        return self._all

    def random(self, difficulty: Optional[str] = None) -> dict:
        pool = [s for s in self._all if s["difficulty"] == difficulty] if difficulty else self._all
        return random.choice(pool or self._all)


_sentence_bank = SentenceBank()


# ── Local Accent Calibration hook (US-90 — not built yet) ────────────────────────────
def apply_accent_calibration(
    word_results: List[WordResultSchema], accent_profile: Optional[str]
) -> List[WordResultSchema]:
    """Stub: once US-90's calibration model exists, this is where accent-specific
    thresholds/expected pronunciation variants get applied before scoring is finalized.
    No-op today so `accent_profile` can be threaded through the API now without another
    interface change once the real model lands."""
    return word_results


def _classify_word(
    aligned: text_alignment.AlignedWord,
    transcript_words,
    prosody: prosody_engine.ProsodyData,
    config,
) -> WordResultSchema:
    timing = transcript_words[aligned.transcript_index] if aligned.transcript_word is not None else None
    status = recording_engine.classify_word_status(aligned.target_word, timing, prosody, config)
    return WordResultSchema(
        word=aligned.target_word,
        target_index=aligned.target_index,
        status=status.value,
        confidence=round(timing.probability, 3) if timing is not None else None,
    )


def _overall_score(word_results: List[WordResultSchema]) -> float:
    if not word_results:
        return 0.0
    points = [_STATUS_POINTS[WordStatus(w.status)] for w in word_results]
    return round(sum(points) / len(points), 2)


async def get_target_sentence(sentence_id: Optional[str] = None, difficulty: Optional[str] = None):
    if sentence_id:
        sentence = _sentence_bank.get_by_id(sentence_id)
        if not sentence:
            raise SentenceNotFoundError(f"Unknown sentence_id: {sentence_id}")
    else:
        sentence = _sentence_bank.random(difficulty)
    return TargetSentenceSchema(**sentence)


async def submit_pronunciation_attempt(
    sentence_id: str,
    audio: UploadFile = File(...),
    accent_profile: Optional[str] = Form(None),
    user_id: str = Depends(require_auth),
):
    sentence = _sentence_bank.get_by_id(sentence_id)
    if not sentence:
        raise SentenceNotFoundError(f"Unknown sentence_id: {sentence_id}")

    config = load_speech_config()
    audio_bytes = await audio.read()
    max_bytes = config.pronunciation_max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise UploadTooLargeError(f"Recording exceeds the {config.pronunciation_max_upload_mb}MB limit")

    try:
        analysis = recording_engine.analyze_recording(audio_bytes, config)
    except AudioDecodeError as e:
        raise UnreadableAudioError(str(e))

    if analysis.rejection is not None:
        return JSONResponse(
            status_code=422,
            content=RecordingRejectedSchema(
                reason=analysis.rejection.value,
                message=_rejection_message(analysis.rejection),
            ).model_dump(),
        )

    aligned_words = recording_engine.align_to_sentence(analysis, sentence["text"])

    word_results = [_classify_word(a, analysis.words, analysis.prosody, config) for a in aligned_words]
    word_results = apply_accent_calibration(word_results, accent_profile)

    disfluency_detected = recording_engine.detect_disfluency(analysis, config)
    overall_score = _overall_score(word_results)

    accent_profile_tag = accent_profile or config.default_accent_profile

    existing = await db.pronunciationattempt.find_unique(
        where={"userId_sentenceId": {"userId": user_id, "sentenceId": sentence_id}}
    )
    data = {
        "targetText": sentence["text"],
        "transcript": analysis.transcript,
        "wordResults": Json([w.model_dump() for w in word_results]),
        "overallScore": overall_score,
        "accentProfileTag": accent_profile_tag,
        "backgroundVoiceDetected": analysis.multiple_voices_detected,
        "disfluencyDetected": disfluency_detected,
    }

    if existing:
        attempt = await db.pronunciationattempt.update(
            where={"id": existing.id},
            data={**data, "attemptCount": existing.attemptCount + 1},
        )
    else:
        attempt = await db.pronunciationattempt.create(
            data={"userId": user_id, "sentenceId": sentence_id, "attemptCount": 1, **data}
        )

    return PronunciationResultSchema(
        attempt_id=attempt.id,
        sentence_id=sentence_id,
        target_text=sentence["text"],
        transcript=analysis.transcript,
        overall_score=overall_score,
        word_results=word_results,
        attempt_count=attempt.attemptCount,
        background_voice_detected=analysis.multiple_voices_detected,
        disfluency_detected=disfluency_detected,
        accent_profile=accent_profile_tag,
    )


def _rejection_message(reason: RejectionReason) -> str:
    return {
        RejectionReason.NO_SPEECH_DETECTED: "No speech was detected in the recording. Please try again.",
        RejectionReason.AUDIO_TOO_QUIET: "The recording is too quiet to analyze. Please move closer to the microphone.",
        RejectionReason.BACKGROUND_NOISE_TOO_HIGH: "Background noise is too high to analyze. Please try again in a quieter environment.",
        RejectionReason.INCOMPLETE_RECORDING: "The recording appears to be incomplete.",
        RejectionReason.MULTIPLE_VOICES_DETECTED: "Multiple voices were detected in the recording.",
    }[reason]
