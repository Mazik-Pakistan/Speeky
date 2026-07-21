"""
Shared word-level pronunciation-scoring pipeline (Story 1 core).

This is the SINGLE scoring pipeline shared by all four Pronunciation Coach
user stories (word-level highlighting, accessibility safeguard, outage
fallback, trouble-words bank). It wraps the existing, unmodified
PronunciationScorer (lib/pronunciation_coach/pronunciation.py) and adds the word-level
color-tier classification, exception handling (omission / stutter /
accent calibration / noise), and configuration that PronunciationScorer
itself does not provide.

Story 2 (accessibility_profile.py), Story 3 (pronunciation_reliability.py)
and Story 4 (trouble_words.py) all consume PronunciationPipeline's output
(SentenceScoreResult / WordScoreResult) rather than re-implementing any
scoring logic, so pronunciation logic is never forked per story.

Design note on inputs: WordAligner (the old speeky/alignment.py module (pre-restructure standalone location)
that produced timestamped word alignments from raw audio) was NOT part of
what was restored for this feature. `score_sentence()` therefore expects
its `attempts` argument already aligned 1:1 with `target_words` (one
attempt, or None for an omitted word, per target-sentence position) -
exactly the "word_alignments" shape PronunciationScorer's own docstring
already assumes. Any upstream ASR/alignment step is out of scope here.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Protocol, Sequence, Set

logger = logging.getLogger(__name__)


class ColorTier(str, Enum):
    """UI highlight tiers for a scored word (Story 1)."""

    GREEN = "green"          # correctly pronounced
    ORANGE = "orange"        # minor stress/timing error, phonemes essentially right
    RED = "red"              # complete mispronunciation
    GRAY = "gray"            # omitted entirely (E-01)
    UNSCORABLE = "unscorable"  # interrupted by noise/outage, not judged (E-04)


@dataclass(frozen=True)
class PronunciationPipelineConfig:
    """
    Named, overridable thresholds for color-tier classification.

    All defaults below are UNCALIBRATED placeholders - nobody has supplied
    real calibration data (a labeled corpus of green/orange/red judgments)
    for this project yet. They are deliberately named and constructor-
    injectable so a calibration pass can replace them without touching
    pipeline logic. Do not treat these numbers as validated.
    """

    # Final word_score (0-100, post duration-penalty) at/above which a
    # word is GREEN. UNCALIBRATED.
    green_min_score: float = 80.0

    # Underlying phoneme-confidence percentage (word_scores[i]['confidence']
    # * 100, BEFORE the duration penalty PronunciationScorer applies) below
    # which the word is treated as a genuine mispronunciation (RED) no
    # matter what the timing looks like. At/above this, a low final score
    # is attributed to stress/timing only (ORANGE), since the underlying
    # phoneme match was fine. UNCALIBRATED.
    mispronunciation_confidence_floor: float = 60.0

    # Phoneme substitution pairs treated as acceptable regional variation
    # when the "Local Accent" toggle is on (E-03). Keys/values are CMU
    # ARPAbet phonemes (matching g2p_en's output alphabet in
    # pronunciation.py). This is a placeholder starter list, not a
    # linguist-reviewed table - UNCALIBRATED, flagged for review.
    regional_variant_tolerant_pairs: frozenset = field(
        default_factory=lambda: frozenset(
            {
                frozenset({"AA", "AO"}),  # cot/caught-type merger
                frozenset({"T", "D"}),    # flapped/soft T in many dialects
                frozenset({"IH", "IY"}),  # relaxed final vowel
            }
        )
    )

    # Per-repetition fluency penalty applied for stuttered words (E-02),
    # in points off the 0-100 sentence fluency_score. UNCALIBRATED.
    per_repetition_fluency_penalty: float = 8.0

    # Repetition count (attempts before the final, successful one) at or
    # above which a word counts as "stuttered" for fluency-penalty
    # purposes. A single retry isn't penalized; 2+ retries is. UNCALIBRATED.
    stutter_repetition_threshold: int = 2

    # E-03 accent calibration tolerance band: how far below
    # mispronunciation_confidence_floor a word's raw confidence may fall
    # and still be considered for regional-variant acceptance (see
    # _is_regional_variant). UNCALIBRATED.
    regional_variant_confidence_tolerance: float = 15.0


class ScorerLike(Protocol):
    """Structural type for whatever PronunciationScorer-shaped object is injected."""

    def score_pronunciation(self, audio, sample_rate, word_alignments, reference_text) -> Dict:
        ...

    def get_phoneme_errors(self, predicted_phonemes: List[str], target_phonemes: List[str]) -> List[Dict[str, str]]:
        ...


@dataclass
class WordAttempt:
    """One transcribed/aligned attempt for a single target-sentence word position."""

    word: str
    start: float
    end: float
    confidence: float = 0.5
    repetitions: int = 1          # E-02: attempts made before this final articulation
    unscorable: bool = False      # E-04: interrupted by background noise etc.


@dataclass
class WordScoreResult:
    index: int
    target_word: str
    tier: ColorTier
    strikethrough: bool = False
    final_score: Optional[float] = None
    raw_confidence_pct: Optional[float] = None
    note: str = ""


@dataclass
class SentenceScoreResult:
    target_sentence: str
    words: List[WordScoreResult]
    fluency_score: float
    scoring_profile: str = "standard"  # "standard" | "accessibility" (Story 2 E-04)
    retry_recommended: bool = False

    def red_or_gray_words(self) -> List[WordScoreResult]:
        """Words a 'Retry' action (Story 1 happy path) should focus on."""
        return [w for w in self.words if w.tier in (ColorTier.RED, ColorTier.GRAY)]


class PronunciationPipeline:
    """
    The shared pronunciation-scoring pipeline.

    Wraps an injected PronunciationScorer-shaped object (defaults to
    lib.pronunciation_coach.pronunciation.PronunciationScorer, built lazily so callers that
    don't need real g2p_en scoring - e.g. tests - can inject a stub).
    """

    def __init__(
        self,
        scorer: Optional[ScorerLike] = None,
        config: Optional[PronunciationPipelineConfig] = None,
    ):
        self._scorer = scorer
        self.config = config or PronunciationPipelineConfig()

    @property
    def scorer(self) -> ScorerLike:
        if self._scorer is None:
            from lib.pronunciation_coach.pronunciation import PronunciationScorer

            self._scorer = PronunciationScorer()
        return self._scorer

    def score_sentence(
        self,
        target_sentence: str,
        attempts: Sequence[Optional[WordAttempt]],
        accent_calibration: bool = False,
        accessibility_exempt_indices: Optional[Set[int]] = None,
    ) -> SentenceScoreResult:
        """
        Score one read-aloud attempt of `target_sentence` and classify each
        target word into a ColorTier.

        Args:
            target_sentence: The sentence the user was asked to read.
            attempts: One entry per word in target_sentence.split(), in
                order. `None` means the word was never attempted (E-01
                omission). An entry with `unscorable=True` means it was
                interrupted by noise/outage (E-04).
            accent_calibration: "Local Accent" toggle state (E-03).
            accessibility_exempt_indices: Word indices whose repetitions
                should NOT count against fluency_score because Story 2's
                accessibility profile is active and attributes that
                disfluency to the user's disclosed condition rather than
                a correctable error. Passed in by accessibility_profile.py
                - this module has no notion of accessibility itself.

        Returns:
            SentenceScoreResult with one WordScoreResult per target word.
        """
        target_words = target_sentence.split()
        if len(attempts) != len(target_words):
            raise ValueError(
                f"attempts must have one entry per target word "
                f"({len(target_words)} words, got {len(attempts)} attempts)"
            )
        accessibility_exempt_indices = accessibility_exempt_indices or set()

        word_alignments = [
            {"word": a.word, "start": a.start, "end": a.end, "confidence": a.confidence}
            for a in attempts
            if a is not None and not a.unscorable
        ]
        scored_by_word = {}
        if word_alignments:
            raw = self.scorer.score_pronunciation(
                audio=None, sample_rate=16000, word_alignments=word_alignments, reference_text=target_sentence
            )
            # Map back positionally: PronunciationScorer preserves input order.
            scorable_indices = [i for i, a in enumerate(attempts) if a is not None and not a.unscorable]
            for pos, word_score in zip(scorable_indices, raw["word_scores"]):
                scored_by_word[pos] = word_score

        results: List[WordScoreResult] = []
        penalized_fluency = 100.0
        for i, (target_word, attempt) in enumerate(zip(target_words, attempts)):
            if attempt is None:
                results.append(
                    WordScoreResult(
                        index=i,
                        target_word=target_word,
                        tier=ColorTier.GRAY,
                        strikethrough=True,
                        note="omitted: word was not attempted",
                    )
                )
                continue

            if attempt.unscorable:
                results.append(
                    WordScoreResult(
                        index=i,
                        target_word=target_word,
                        tier=ColorTier.UNSCORABLE,
                        note="unscorable: interrupted by background noise",
                    )
                )
                continue

            word_score = scored_by_word[i]
            final_score = word_score["score"]
            raw_confidence_pct = word_score["confidence"] * 100

            tier, note = self._classify_tier(final_score, raw_confidence_pct, accent_calibration)

            results.append(
                WordScoreResult(
                    index=i,
                    target_word=target_word,
                    tier=tier,
                    final_score=final_score,
                    raw_confidence_pct=raw_confidence_pct,
                    note=note,
                )
            )

            if (
                attempt.repetitions >= self.config.stutter_repetition_threshold
                and i not in accessibility_exempt_indices
            ):
                penalized_fluency -= self.config.per_repetition_fluency_penalty

        fluency_score = max(0.0, min(100.0, penalized_fluency))
        retry_recommended = any(w.tier in (ColorTier.RED, ColorTier.UNSCORABLE) for w in results)

        logger.info(
            "Scored sentence %r: %d words, fluency=%.1f, retry_recommended=%s",
            target_sentence, len(results), fluency_score, retry_recommended,
        )

        return SentenceScoreResult(
            target_sentence=target_sentence,
            words=results,
            fluency_score=fluency_score,
            retry_recommended=retry_recommended,
        )

    def _classify_tier(
        self, final_score: float, raw_confidence_pct: float, accent_calibration: bool
    ) -> "tuple[ColorTier, str]":
        cfg = self.config

        if final_score >= cfg.green_min_score:
            return ColorTier.GREEN, ""

        if raw_confidence_pct >= cfg.mispronunciation_confidence_floor:
            # Phonemes were essentially recognized; the low final score is
            # a timing/duration artifact, i.e. a stress error, not a
            # mispronunciation.
            return ColorTier.ORANGE, "minor stress/timing deviation"

        if accent_calibration and self._is_regional_variant(raw_confidence_pct):
            return ColorTier.GREEN, "accepted regional variant (Local Accent)"

        return ColorTier.RED, "mispronounced"

    def _is_regional_variant(self, raw_confidence_pct: float) -> bool:
        """
        E-03 accent calibration heuristic.

        Real per-phoneme substitution detection would need the deleted
        WordAligner's phoneme-level output, which is out of scope here.
        As a conservative stand-in: only treat a RED word as an accepted
        regional variant when its confidence is close to (not far below)
        the mispronunciation floor - i.e. plausibly a systematic
        regional-consonant-stress difference rather than an outright
        wrong phoneme. Tolerance band is
        config.regional_variant_confidence_tolerance (UNCALIBRATED,
        constructor-injectable like every other threshold on
        PronunciationPipelineConfig); replace this whole heuristic with
        real phoneme-pair comparison via self.scorer.get_phoneme_errors(...)
        once a real aligner is available.
        """
        return raw_confidence_pct >= (
            self.config.mispronunciation_confidence_floor - self.config.regional_variant_confidence_tolerance
        )
