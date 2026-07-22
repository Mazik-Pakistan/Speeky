"""
Accent Assessment — Rhythm & Stress Patterns (US-93): read a longer passage aloud,
get 4 separate dimension scores (pronunciation, stress pattern, rhythm, intonation,
clarity) plus weak-point detection. Built on lib/recording_engine.py (Story #1) and
reuses lib/recording_engine.classify_word_status — the same per-word classification
Pronunciation Coach uses — rather than a second copy of that logic.

A completed assessment automatically generates an Accent Profile (US-89) via
services/accent_profile_service.py.
"""

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, File, UploadFile
from fastapi.responses import JSONResponse
from prisma import Json

from lib import prosody_engine, recording_engine, text_alignment
from lib.audio_io import AudioDecodeError
from lib.prisma_client import db
from lib.recording_engine import RecordingAnalysis, RejectionReason
from lib.speech_config import SpeechConfig, load_speech_config
from lib.text_alignment import AlignedWord, WordStatus
from middlewares.auth_middleware import require_auth
from prisma.enums import AccentAssessmentStatus
from schemas.accent_schemas import (
    AccentAssessmentResultSchema,
    RecordingRejectedSchema,
    TargetPassageSchema,
    WeakPointSchema,
)
from utils.feature_errors import PassageNotFoundError, UnreadableAudioError, UploadTooLargeError

logger = logging.getLogger(__name__)

_REJECTION_TO_STATUS = {
    RejectionReason.NO_SPEECH_DETECTED: AccentAssessmentStatus.REJECTED_NO_SPEECH,
    RejectionReason.AUDIO_TOO_QUIET: AccentAssessmentStatus.REJECTED_TOO_QUIET,
    RejectionReason.BACKGROUND_NOISE_TOO_HIGH: AccentAssessmentStatus.REJECTED_TOO_NOISY,
    RejectionReason.INCOMPLETE_RECORDING: AccentAssessmentStatus.REJECTED_INCOMPLETE,
    RejectionReason.MULTIPLE_VOICES_DETECTED: AccentAssessmentStatus.REJECTED_MULTIPLE_VOICES,
}

_REJECTION_MESSAGES = {
    RejectionReason.NO_SPEECH_DETECTED: "No speech was detected in the recording. Please try again.",
    RejectionReason.AUDIO_TOO_QUIET: "The recording is too quiet to analyze. Please move closer to the microphone.",
    RejectionReason.BACKGROUND_NOISE_TOO_HIGH: "Background noise is too high to analyze. Please try again in a quieter environment.",
    RejectionReason.INCOMPLETE_RECORDING: "The reading appears incomplete — please read the entire passage in one take.",
    RejectionReason.MULTIPLE_VOICES_DETECTED: "Multiple voices were detected in the recording. Please record alone in a quiet space.",
}


class PassageBank:
    def __init__(self):
        path = Path(__file__).parent.parent / "data" / "accent_passages.json"
        with open(path, "r", encoding="utf-8") as f:
            raw: Dict[str, List[dict]] = json.load(f)
        self._by_id = {p["passage_id"]: p for passages in raw.values() for p in passages}
        self._all = list(self._by_id.values())

    def get_by_id(self, passage_id: str) -> Optional[dict]:
        return self._by_id.get(passage_id)

    def random(self, difficulty: Optional[str] = None) -> dict:
        pool = [p for p in self._all if p["difficulty"] == difficulty] if difficulty else self._all
        return random.choice(pool or self._all)


_passage_bank = PassageBank()


async def get_target_passage(passage_id: Optional[str] = None, difficulty: Optional[str] = None):
    if passage_id:
        passage = _passage_bank.get_by_id(passage_id)
        if not passage:
            raise PassageNotFoundError(f"Unknown passage_id: {passage_id}")
    else:
        passage = _passage_bank.random(difficulty)
    return TargetPassageSchema(**passage)


# ── Dimension scoring ────────────────────────────────────────────────────────────────
def _pronunciation_score(aligned_words: List[AlignedWord], transcript_words) -> float:
    matched = [a for a in aligned_words if a.transcript_word is not None]
    if not matched:
        return 0.0
    confidences = [transcript_words[a.transcript_index].probability for a in matched]
    return round(100.0 * (sum(confidences) / len(confidences)), 2)


def _stress_score(aligned_words: List[AlignedWord], config: SpeechConfig, prosody, transcript_words) -> float:
    checkable = 0
    within_tolerance = 0
    for a in aligned_words:
        if a.transcript_word is None:
            continue
        expected = text_alignment.expected_stress_position(a.target_word)
        if expected is None:
            continue
        timing = transcript_words[a.transcript_index]
        peak_pos = prosody_engine.word_stress_peak_position(prosody, timing.start, timing.end)
        if peak_pos is None:
            continue
        checkable += 1
        if abs(peak_pos - expected) <= config.stress_error_sensitivity:
            within_tolerance += 1
    if checkable == 0:
        # No multisyllabic in-dictionary words could be checked -- neutral score,
        # not a penalty for something we couldn't measure.
        return 100.0
    return round(100.0 * (within_tolerance / checkable), 2)


def _rhythm_score(prosody, config: SpeechConfig) -> float:
    """rhythm_max_acceptable_cv=2.0 (not something smaller/more "intuitive" like 0.5) is
    an empirical default, not a guess: natural fluent English speech has real, expected
    variation in inter-syllable timing from phrase-boundary pauses and vowel reduction
    on unstressed syllables -- checked against five real recorded samples during review,
    coefficient of variation landed between 0.5 and 0.9 on all of them. A 0.5 ceiling
    would floor the rhythm score near zero for essentially any real speech; 2.0 leaves
    normal fluent delivery in a reasonable 55-75 range and still penalizes genuinely
    erratic timing well above that.
    """
    cv = prosody_engine.rhythm_coefficient_of_variation(prosody.syllable_nuclei_times)
    if cv is None:
        return 70.0  # not enough syllable nuclei to measure reliably -- moderate default
    score = 100.0 * (1.0 - min(cv, config.rhythm_max_acceptable_cv) / config.rhythm_max_acceptable_cv)
    return round(max(0.0, min(100.0, score)), 2)


def _intonation_score(prosody, config: SpeechConfig) -> float:
    lo, hi = config.intonation_ideal_range_min_semitones, config.intonation_ideal_range_max_semitones
    pitch_range = prosody.pitch_range_semitones
    if lo <= pitch_range <= hi:
        return 100.0
    if pitch_range < lo:
        return round(max(0.0, 100.0 * (pitch_range / lo)), 2) if lo > 0 else 0.0
    excess = pitch_range - hi
    return round(max(0.0, 100.0 - (excess / hi) * 100.0), 2) if hi > 0 else 0.0


def _clarity_score(aligned_words: List[AlignedWord], config: SpeechConfig) -> float:
    total = len(aligned_words)
    if total == 0:
        return 0.0
    misses = 0.0
    for a in aligned_words:
        if a.transcript_word is not None:
            continue
        syllables = text_alignment.syllable_count(a.target_word) or 1
        if syllables >= config.multisyllabic_min_syllables:
            misses += config.clarity_skipped_multisyllabic_penalty_weight
        else:
            misses += 1.0
    return round(max(0.0, 100.0 * (1.0 - misses / total)), 2)


def _weak_points(
    aligned_words: List[AlignedWord],
    transcript_words,
    prosody,
    config: SpeechConfig,
    rhythm_score: float,
    intonation_score: float,
) -> List[WeakPointSchema]:
    points: List[WeakPointSchema] = []

    th_mispronounced = [
        a.target_word
        for a in aligned_words
        if a.transcript_word is not None
        and "th" in a.target_word.lower()
        and recording_engine.classify_word_status(a.target_word, transcript_words[a.transcript_index], prosody, config)
        == WordStatus.MISPRONOUNCED
    ]
    if len(th_mispronounced) >= 2:
        points.append(WeakPointSchema(issue="th sound", detail=f"Mispronounced: {', '.join(th_mispronounced[:5])}"))

    stress_error_words = [
        a.target_word
        for a in aligned_words
        if a.transcript_word is not None
        and recording_engine.classify_word_status(a.target_word, transcript_words[a.transcript_index], prosody, config)
        == WordStatus.STRESS_ERROR
    ]
    if len(stress_error_words) >= 2:
        points.append(
            WeakPointSchema(issue="word-final stress", detail=f"Stress placement was off on: {', '.join(stress_error_words[:5])}")
        )

    skipped_multisyllabic = [
        a.target_word
        for a in aligned_words
        if a.transcript_word is None and (text_alignment.syllable_count(a.target_word) or 1) >= config.multisyllabic_min_syllables
    ]
    if skipped_multisyllabic:
        points.append(
            WeakPointSchema(issue="multisyllabic word clarity", detail=f"Skipped or unclear: {', '.join(skipped_multisyllabic[:5])}")
        )

    if rhythm_score < 60.0:
        points.append(WeakPointSchema(issue="speech rhythm", detail="Syllable timing was noticeably irregular across the passage"))

    if intonation_score < 60.0:
        direction = "flat/monotone" if prosody.pitch_range_semitones < config.intonation_ideal_range_min_semitones else "erratic"
        points.append(WeakPointSchema(issue="intonation range", detail=f"Pitch variation was {direction} across the passage"))

    return points


async def submit_passage_assessment(
    passage_id: str,
    audio: UploadFile = File(...),
    user_id: str = Depends(require_auth),
):
    passage = _passage_bank.get_by_id(passage_id)
    if not passage:
        raise PassageNotFoundError(f"Unknown passage_id: {passage_id}")

    config = load_speech_config()
    audio_bytes = await audio.read()
    max_bytes = config.accent_max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise UploadTooLargeError(f"Recording exceeds the {config.accent_max_upload_mb}MB limit")

    try:
        analysis = recording_engine.analyze_recording(audio_bytes, config)
    except AudioDecodeError as e:
        raise UnreadableAudioError(str(e))

    aligned_words, coverage = recording_engine.align_to_passage(analysis, passage["text"], config)

    rejection = analysis.rejection
    if rejection is None and analysis.multiple_voices_detected:
        rejection = RejectionReason.MULTIPLE_VOICES_DETECTED
    if rejection is None and (
        coverage.coverage_ratio < config.passage_min_coverage
        or coverage.trailing_coverage_ratio < config.passage_min_coverage
    ):
        rejection = RejectionReason.INCOMPLETE_RECORDING

    if rejection is not None:
        await db.accentassessment.create(
            data={
                "userId": user_id,
                "passageId": passage_id,
                "status": _REJECTION_TO_STATUS[rejection],
                "rejectionReason": rejection.value,
                "transcript": analysis.transcript or None,
            }
        )
        return JSONResponse(
            status_code=422,
            content=RecordingRejectedSchema(reason=rejection.value, message=_REJECTION_MESSAGES[rejection]).model_dump(),
        )

    pronunciation_score = _pronunciation_score(aligned_words, analysis.words)
    stress_score = _stress_score(aligned_words, config, analysis.prosody, analysis.words)
    rhythm_score = _rhythm_score(analysis.prosody, config)
    intonation_score = _intonation_score(analysis.prosody, config)
    clarity_score = _clarity_score(aligned_words, config)
    weak_points = _weak_points(aligned_words, analysis.words, analysis.prosody, config, rhythm_score, intonation_score)

    assessment = await db.accentassessment.create(
        data={
            "userId": user_id,
            "passageId": passage_id,
            "status": AccentAssessmentStatus.COMPLETED,
            "transcript": analysis.transcript,
            "pronunciationScore": pronunciation_score,
            "stressScore": stress_score,
            "rhythmScore": rhythm_score,
            "intonationScore": intonation_score,
            "clarityScore": clarity_score,
            "weakPoints": Json([w.model_dump() for w in weak_points]),
            "completedAt": datetime.now(timezone.utc),
        }
    )

    # Local import breaks the accent_assessment/accent_profile import cycle -- profile
    # generation is US-89's job, triggered here the same way assessment_service.py
    # triggers reassessment_service's regression check after a completed baseline.
    from services import accent_profile_service

    await accent_profile_service.generate_profile_from_assessment(assessment)

    return AccentAssessmentResultSchema(
        assessment_id=assessment.id,
        passage_id=passage_id,
        status="completed",
        transcript=analysis.transcript,
        pronunciation_score=pronunciation_score,
        stress_score=stress_score,
        rhythm_score=rhythm_score,
        intonation_score=intonation_score,
        clarity_score=clarity_score,
        weak_points=weak_points,
    )
