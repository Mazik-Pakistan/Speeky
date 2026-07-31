"""
Session scoring — the split between the TEXT-input and AUDIO-input pipelines.

The confidence engine (lib/confidence_engine.py) aggregates fluency/vocabulary/
pronunciation into a top-line score, but it does not know how those component scores
are produced. This module produces them, and it is where the two pipelines diverge:

  TEXT pipeline (typed drafts — email writing, typed workplace practice):
    - No audio signal, so pronunciation is None and the confidence engine renormalizes
      fluency+vocabulary to 100% (see confidence_engine.calculate_session_confidence).
    - "fluency" is a WRITTEN-fluency proxy (length adequacy, lexical diversity, sentence
      structure) rather than speech timing.

  AUDIO pipeline (spoken submissions — meetings, presentations, client roleplay):
    - Fluency comes from speech-delivery signals produced upstream by the Livekit +
      SileroVAD + faster-whisper agent (speech-to-text/agent.py): word timings / pauses /
      filler words. The scoring bands mirror speeky/fluency.py exactly.
    - Pronunciation is taken from the pronunciation scorer if the agent supplies it, else a
      delivery-derived proxy — either way it is present, so the full 50/30/20 weighting runs.

Both paths return a ScoredSession carrying a confidence_engine.SessionScore plus the
delivery detail the coaching feedback layer surfaces (hesitation, timing).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from lib.confidence_engine import SessionScore

# multi-word fillers checked separately
_FILLER_PHRASES = ["you know", "i mean", "sort of", "kind of"]

# Ideal spoken pace (words/sec) — mirrors speeky/fluency.py.
_PAUSE_THRESHOLD_S = 0.2


@dataclass
class AudioFeatures:
    """Audio-derived signal handed to the backend by the STT/VAD agent.

    Everything here is already extracted upstream (WebRTC → SileroVAD segments →
    faster-whisper word timestamps); the backend never touches raw audio. Callers may
    provide word_timings and let this module derive speech_rate/pause_count, or provide
    the aggregate metrics directly.
    """

    transcript: str
    duration_seconds: float = 0.0
    word_timings: List[Dict] = field(default_factory=list)  # [{"word","start","end"}]
    speech_rate: Optional[float] = None
    pause_count: Optional[int] = None
    mean_pause_duration: Optional[float] = None
    filled_pauses: Optional[int] = None
    avg_db: Optional[float] = None  # mean input level; low ⇒ mic muted/quiet (WEC-US-12 E-04)
    pronunciation_score: Optional[float] = None  # from the pronunciation scorer, if run


@dataclass
class ScoredSession:
    fluency_score: float
    vocabulary_score: float
    pronunciation_score: Optional[float]
    is_text_only: bool
    delivery: Dict = field(default_factory=dict)

    def to_session_score(self, is_complete: bool = True) -> SessionScore:
        return SessionScore(
            timestamp=datetime.now(timezone.utc),
            fluency_score=self.fluency_score,
            vocabulary_score=self.vocabulary_score,
            pronunciation_score=self.pronunciation_score,
            is_text_only=self.is_text_only,
            is_complete=is_complete,
        )


# ── Shared: vocabulary ────────────────────────────────────────────────────────
def estimate_vocabulary_score(text: str) -> float:
    """Lexical-diversity + word-length heuristic (shared with assessment_service)."""
    if not text:
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    unique_words = len(set(w.lower() for w in words))
    total_words = len(words)
    lexical_diversity = unique_words / total_words
    avg_word_length = sum(len(w) for w in words) / total_words
    return round((lexical_diversity * 50) + (min(avg_word_length / 8, 1) * 50), 2)


def _type_token_ratio(text: str) -> float:
    words = [w.lower() for w in re.findall(r"[a-zA-Z']+", text)]
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def count_filled_pauses(transcript: str) -> int:
    """Count filler words/phrases in a transcript (mirrors speeky/fluency.py list)."""
    if not transcript:
        return 0
    lowered = transcript.lower()
    phrase_hits = sum(lowered.count(p) for p in _FILLER_PHRASES)
    tokens = re.findall(r"[a-z]+", lowered)
    single = {"um", "uh", "er", "erm", "ah", "like"}
    token_hits = sum(1 for t in tokens if t in single)
    return token_hits + phrase_hits


# ── TEXT pipeline ─────────────────────────────────────────────────────────────
def _written_fluency_score(text: str) -> float:
    """Written-fluency proxy (0-100): length adequacy + diversity + sentence structure."""
    words = text.split()
    n = len(words)
    if n == 0:
        return 0.0

    # Length adequacy (40 pts)
    if n >= 40:
        length_pts = 40.0
    elif n >= 20:
        length_pts = 30.0
    elif n >= 10:
        length_pts = 20.0
    else:
        length_pts = 10.0

    # Lexical diversity (30 pts)
    ttr = _type_token_ratio(text)
    if ttr >= 0.6:
        div_pts = 30.0
    elif ttr >= 0.45:
        div_pts = 22.0
    elif ttr >= 0.3:
        div_pts = 15.0
    else:
        div_pts = 8.0

    # Sentence structure (30 pts) — reasonable average sentence length
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    avg_sent = n / len(sentences) if sentences else n
    if 8 <= avg_sent <= 22:
        struct_pts = 30.0
    elif 5 <= avg_sent <= 28:
        struct_pts = 20.0
    else:
        struct_pts = 10.0

    return round(min(100.0, length_pts + div_pts + struct_pts), 2)


def score_text_session(text: str) -> ScoredSession:
    """Score a typed submission (TEXT pipeline). Pronunciation is None by design."""
    return ScoredSession(
        fluency_score=_written_fluency_score(text),
        vocabulary_score=estimate_vocabulary_score(text),
        pronunciation_score=None,
        is_text_only=True,
        delivery={"pipeline": "text", "word_count": len(text.split())},
    )


# ── AUDIO pipeline ────────────────────────────────────────────────────────────
def _derive_timing(features: AudioFeatures) -> Dict:
    """Fill speech_rate / pause_count / mean_pause_duration from word_timings if absent."""
    speech_rate = features.speech_rate
    pause_count = features.pause_count
    mean_pause = features.mean_pause_duration

    timings = features.word_timings or []
    if timings and (speech_rate is None or pause_count is None):
        first, last = timings[0], timings[-1]
        total = (last.get("end", 0.0) - first.get("start", 0.0)) or features.duration_seconds
        if speech_rate is None and total > 0:
            speech_rate = len(timings) / total
        pauses = []
        for a, b in zip(timings, timings[1:]):
            gap = b.get("start", 0.0) - a.get("end", 0.0)
            if gap > _PAUSE_THRESHOLD_S:
                pauses.append(gap)
        if pause_count is None:
            pause_count = len(pauses)
        if mean_pause is None:
            mean_pause = sum(pauses) / len(pauses) if pauses else 0.0

    # Fall back to overall duration if still unknown.
    if speech_rate is None:
        wc = len(features.transcript.split())
        speech_rate = wc / features.duration_seconds if features.duration_seconds > 0 else 0.0
    if pause_count is None:
        pause_count = 0
    if mean_pause is None:
        mean_pause = 0.0

    return {"speech_rate": speech_rate, "pause_count": pause_count, "mean_pause_duration": mean_pause}


def _audio_fluency_score(speech_rate: float, pause_count: int, filled_pauses: int, ttr: float) -> float:
    """Fluency 0-100 from delivery signals — bands identical to speeky/fluency.py."""
    score = 0.0
    # Speech rate (40)
    if 2.0 <= speech_rate <= 4.0:
        score += 40.0
    elif 1.5 <= speech_rate <= 5.0:
        score += 30.0
    elif speech_rate > 0:
        score += 20.0
    # Pause frequency (20)
    if pause_count == 0:
        score += 20.0
    elif pause_count <= 2:
        score += 15.0
    elif pause_count <= 5:
        score += 10.0
    else:
        score += 5.0
    # Filled pauses (20)
    if filled_pauses == 0:
        score += 20.0
    elif filled_pauses <= 1:
        score += 15.0
    elif filled_pauses <= 3:
        score += 10.0
    else:
        score += 5.0
    # Lexical diversity (20)
    if ttr >= 0.5:
        score += 20.0
    elif ttr >= 0.4:
        score += 15.0
    elif ttr >= 0.3:
        score += 10.0
    else:
        score += 5.0
    return round(min(100.0, max(0.0, score)), 2)


def _proxy_pronunciation(speech_rate: float, filled_pauses: int, pause_count: int) -> float:
    """Delivery-derived pronunciation proxy when the pronunciation scorer wasn't run.

    Not a phoneme-level score — a clarity stand-in from pace steadiness and disfluency so
    the AUDIO pipeline still carries a pronunciation component (keeps the 50/30/20 weighting
    intact instead of silently degrading to the text-only renormalization).
    """
    score = 70.0
    if 2.0 <= speech_rate <= 4.0:
        score += 15.0
    elif speech_rate > 0:
        score += 5.0
    else:
        score -= 20.0
    score -= min(20.0, filled_pauses * 4.0)
    score -= min(15.0, max(0, pause_count - 3) * 2.0)
    return round(min(100.0, max(0.0, score)), 2)


def aggregate_audio_turns(turns: List[AudioFeatures]) -> AudioFeatures:
    """Combine per-turn audio signal into one AudioFeatures for whole-session scoring.

    Derives timing per turn (not by concatenating word_timings across turns) because a
    turn boundary includes the AI's reply — gluing raw timings would count that gap as
    user pause time.
    """
    audio_turns = [t for t in turns if t.duration_seconds > 0 or t.word_timings]
    full_transcript = " ".join(t.transcript for t in turns if t.transcript)
    if not audio_turns:
        return AudioFeatures(transcript=full_transcript)

    total_duration = sum(t.duration_seconds for t in audio_turns)
    total_words = 0
    total_pauses = 0
    pause_time = 0.0
    for t in audio_turns:
        timing = _derive_timing(t)
        total_words += len(t.transcript.split())
        total_pauses += timing["pause_count"]
        pause_time += timing["pause_count"] * timing["mean_pause_duration"]

    return AudioFeatures(
        transcript=full_transcript,
        duration_seconds=total_duration,
        speech_rate=(total_words / total_duration) if total_duration > 0 else 0.0,
        pause_count=total_pauses,
        mean_pause_duration=(pause_time / total_pauses) if total_pauses > 0 else 0.0,
        filled_pauses=count_filled_pauses(full_transcript),
    )


def score_audio_session(features: AudioFeatures) -> ScoredSession:
    """Score a spoken submission (AUDIO pipeline) from agent-supplied features."""
    timing = _derive_timing(features)
    speech_rate = timing["speech_rate"]
    pause_count = timing["pause_count"]

    filled = features.filled_pauses
    if filled is None:
        filled = count_filled_pauses(features.transcript)

    ttr = _type_token_ratio(features.transcript)
    fluency = _audio_fluency_score(speech_rate, pause_count, filled, ttr)
    vocabulary = estimate_vocabulary_score(features.transcript)

    pronunciation = features.pronunciation_score
    if pronunciation is None:
        pronunciation = _proxy_pronunciation(speech_rate, filled, pause_count)

    return ScoredSession(
        fluency_score=fluency,
        vocabulary_score=vocabulary,
        pronunciation_score=pronunciation,
        is_text_only=False,
        delivery={
            "pipeline": "audio",
            "speech_rate": round(speech_rate, 2),
            "pause_count": pause_count,
            "mean_pause_duration": round(timing["mean_pause_duration"], 2),
            "filled_pauses": filled,
            "duration_seconds": round(features.duration_seconds, 2),
            "word_count": len(features.transcript.split()),
            "pronunciation_estimated": features.pronunciation_score is None,
        },
    )
