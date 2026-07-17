"""
Real-Time Inline Grammar Correction Toggle (US-27 / PDF GAP-04).

Reuses GrammarCorrector for the actual correction. This module only adds
the "chip" layer on top: opt-in gating, picking the single highest-impact
error, suppressing false positives, and voice-mode suppression. No new
grammar-checking logic is implemented here.
"""

import difflib
import logging
from typing import Dict, List, Optional

from .grammar import GrammarCorrector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InlineCorrectionChipService:
    """
    Produces a single inline correction chip from GrammarCorrector's output,
    gated by the user's toggle setting and current mode (voice vs. text).
    """

    def __init__(self, grammar_corrector: Optional[GrammarCorrector] = None):
        """
        Args:
            grammar_corrector: Reuse an existing GrammarCorrector instance
                (e.g. the one pipeline.py already loads) instead of
                constructing a second one. Falls back to a new instance
                only if none is passed.
        """
        self.grammar_corrector = grammar_corrector or GrammarCorrector()

    def get_correction_chip(
        self,
        original_text: str,
        show_corrections_enabled: bool = False,
        is_voice_mode: bool = False,
        use_llm: bool = True,
    ) -> Dict[str, any]:
        """
        Run grammar correction and return a single chip, or none, per US-27.

        Args:
            original_text: The learner's just-submitted message.
            show_corrections_enabled: The user's session-settings toggle
                for "Show corrections during chat". OFF by default per
                acceptance criteria — caller must explicitly pass True.
            is_voice_mode: True if the user is in voice mode. Per E-03,
                chips are suppressed in voice mode (corrections still
                computed and returned for the end-of-session summary,
                just not meant to render inline).
            use_llm: Passed through to GrammarCorrector.correct_text().

        Returns:
            Dict with:
                - grammar_result: full GrammarCorrector output (always
                  present — used for the end-of-session summary regardless
                  of toggle state, per Happy Path step 5)
                - chip: {"from": str, "to": str} for the single
                  highest-impact correction, or None if disabled, no
                  error found, voice mode, or the only diff is a
                  regional-variant false positive
                - suppressed_reason: None, or one of "toggle_off",
                  "voice_mode", "no_correction_needed"
        """
        grammar_result = self.grammar_corrector.correct_text(original_text, use_llm=use_llm)

        if not show_corrections_enabled:
            # Acceptance criteria: off by default, feature must be
            # explicitly enabled. Full result still returned for the
            # end-of-session summary (Happy Path step 5).
            return {"grammar_result": grammar_result, "chip": None, "suppressed_reason": "toggle_off"}

        corrected_text = grammar_result.get("corrected", original_text)

        if original_text.strip() == corrected_text.strip():
            # E-01 (regional variant, e.g. valid British spelling) lands
            # here too: GrammarCorrector already targets British English
            # (see grammar.py's correct_text docstring), so a correct
            # British spelling produces no diff and no false-positive chip.
            # CAVEAT: there's no per-user English-variant setting in
            # grammar.py — it always targets British English. If a
            # learner's variant is set to American, this will NOT behave
            # like the spec's E-01 (it would instead "correct" valid
            # American spelling TO British). Flagging as a gap, not fixed
            # here — needs a variant-aware GrammarCorrector to fully solve.
            return {
                "grammar_result": grammar_result,
                "chip": None,
                "suppressed_reason": "no_correction_needed",
            }

        chip = self._pick_highest_impact_chip(original_text, corrected_text)

        if is_voice_mode:
            # E-03: suppress inline rendering, but keep grammar_result for
            # the summary. Caller is responsible for not rendering `chip`.
            return {"grammar_result": grammar_result, "chip": None, "suppressed_reason": "voice_mode"}

        return {"grammar_result": grammar_result, "chip": chip, "suppressed_reason": None}

    def _pick_highest_impact_chip(self, original: str, corrected: str) -> Optional[Dict[str, str]]:
        """
        Diff original vs. corrected text word-by-word and pick ONE chip
        (E-02: cap to the single highest-impact error on heavily broken
        sentences).

        "Highest-impact" is NOT defined anywhere in the spec — it only
        says "single highest-impact error" without a metric. This uses
        the longest character-length change as a stand-in for impact
        (bigger rewrites assumed more significant than a 1-letter typo).
        TODO: replace with a real severity signal (e.g. from spaCy
        POS-tag category — verb tense vs. article) once one exists.
        """
        original_words = original.split()
        corrected_words = corrected.split()

        matcher = difflib.SequenceMatcher(a=original_words, b=corrected_words)
        candidates: List[Dict[str, str]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            from_phrase = " ".join(original_words[i1:i2])
            to_phrase = " ".join(corrected_words[j1:j2])
            candidates.append({"from": from_phrase, "to": to_phrase})

        if not candidates:
            return None

        # Longest combined length = proxy for "highest impact".
        best = max(candidates, key=lambda c: len(c["from"]) + len(c["to"]))
        return best