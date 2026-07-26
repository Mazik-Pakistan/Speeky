"""
Content-quality / voice-isolation scoring for the Daily Challenge anti-gaming check
(US-168 / GAP-07).

Inputs are real: services/daily_challenge_service._add_turn transcribes each turn's
uploaded audio via lib/recording_engine.py (STT) and runs
lib/prosody_engine.detect_multiple_voices for `non_interactive_audio_signal` — the same
speaker-consistency heuristic services/accent_assessment_service.py uses. This module
never talks to the audio pipeline directly, so it stays trivially unit-testable.

*** HEURISTIC, NOT A TRAINED MODEL ***
`score_engagement_quality`'s repetition-ratio check is a plain token-statistics
heuristic standing in for a real content-quality NLP classifier — genuine semantic
filler detection (as opposed to literal word repetition) is out of scope here. The
function signature and QualityResult contract are the integration point: swap the
repetition check for a real model call later without touching any caller.
"""

from dataclasses import dataclass
from typing import List, Optional

from lib.prompts import (
    DAILY_CHALLENGE_MAX_DOMINANT_TOKEN_RATIO,
    DAILY_CHALLENGE_MIN_UNIQUE_WORD_RATIO,
    DAILY_CHALLENGE_MIN_WORDS_FOR_REPETITION_CHECK,
)

FILLER_REPETITION = "filler_repetition"
NON_INTERACTIVE_AUDIO = "non_interactive_audio"


@dataclass
class TurnSignal:
    """One user turn's worth of signal fed into the quality scorer — both fields are
    real by the time they get here (see module docstring), not client-supplied."""

    text: str
    non_interactive_audio_signal: bool = False


@dataclass
class QualityResult:
    quality: float  # 0-1, higher = more substantive/varied content
    pattern: Optional[str]  # FILLER_REPETITION | NON_INTERACTIVE_AUDIO | None


def score_engagement_quality(turns: List[TurnSignal]) -> QualityResult:
    """Lenient-by-design heuristic: only flags clear repetition/filler patterns or
    non-interactive audio, never low vocabulary/skill level alone (E-01)."""
    if any(t.non_interactive_audio_signal for t in turns):
        return QualityResult(quality=0.0, pattern=NON_INTERACTIVE_AUDIO)

    tokens = [w.lower() for t in turns for w in t.text.split()]
    if not tokens:
        return QualityResult(quality=0.0, pattern=FILLER_REPETITION)

    total = len(tokens)
    unique_ratio = len(set(tokens)) / total

    dominant_count = max((tokens.count(tok) for tok in set(tokens)), default=0)
    dominant_ratio = dominant_count / total

    is_repetitive = (
        total >= DAILY_CHALLENGE_MIN_WORDS_FOR_REPETITION_CHECK
        and (unique_ratio < DAILY_CHALLENGE_MIN_UNIQUE_WORD_RATIO or dominant_ratio > DAILY_CHALLENGE_MAX_DOMINANT_TOKEN_RATIO)
    )
    if is_repetitive:
        return QualityResult(quality=min(unique_ratio, 1 - dominant_ratio), pattern=FILLER_REPETITION)

    # Lenient floor: genuine short/simple answers (beginners) still clear the bar as
    # long as they aren't repetitive — quality reflects variety, not vocabulary level.
    return QualityResult(quality=max(unique_ratio, DAILY_CHALLENGE_MIN_UNIQUE_WORD_RATIO), pattern=None)
