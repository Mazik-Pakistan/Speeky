"""
Assessment Integrity & Anti-Gaming Safeguards (BAS-US-03).

NO LOCAL DOWNLOAD: uses only librosa (already in the approved stack, no
model weights) for audio signal heuristics. NO true TTS/deepfake
classifier exists here — that needs a trained model, explicitly
excluded. This is an APPROXIMATE signal, not certified detection.

NO HARDCODING: all thresholds are constructor params with defaults,
overridable.

REAL LIMITATION — clipboard-paste detection: Python cannot detect "was
this text pasted" from the text itself. That is a frontend-only signal
(JS paste event). This module takes `was_pasted: bool` as INPUT — it
does not, and cannot, detect it itself.
"""

import logging
from typing import Dict, Optional

import numpy as np
import librosa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AssessmentIntegrityChecker:
    """Flags likely synthetic audio or pasted text; tracks repeat offenders. No persistence — in-memory only, flagged."""

    def __init__(
        self,
        pitch_variance_threshold: float = 15.0,
        spectral_flatness_threshold: float = 0.35,
        repeated_flag_threshold: int = 3,
        accessibility_exempt_users: Optional[set] = None,
    ):
        """
        Args:
            pitch_variance_threshold: below this F0 std (Hz), audio is
                suspiciously monotone (TTS signal). Not spec-defined —
                a guess, overridable.
            spectral_flatness_threshold: above this, spectrum is
                suspiciously uniform (TTS signal). Guess, overridable.
            repeated_flag_threshold: E-02's spec number — "3+ sessions".
            accessibility_exempt_users: E-03 — user IDs exempted from
                paste detection. Empty by default; caller manages this
                set (no real account/DB layer exists here).
        """
        self.pitch_variance_threshold = pitch_variance_threshold
        self.spectral_flatness_threshold = spectral_flatness_threshold
        self.repeated_flag_threshold = repeated_flag_threshold
        self.accessibility_exempt_users = accessibility_exempt_users or set()
        self._flag_counts: Dict[str, int] = {}  # TODO: real persistence, not in-memory

    def check_audio(self, audio: np.ndarray, sample_rate: int) -> Dict[str, any]:
        """
        Heuristic synthetic-speech signal via pitch variance + spectral
        flatness (librosa, no downloaded model). E-01: never excludes
        outright — always routes to secondary verification instead.
        """
        try:
            f0, voiced_flag, _ = librosa.pyin(
                audio, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sample_rate
            )
            voiced_f0 = f0[voiced_flag] if voiced_flag is not None else np.array([])
            pitch_std = float(np.nanstd(voiced_f0)) if voiced_f0.size > 0 else 0.0

            flatness = librosa.feature.spectral_flatness(y=audio)
            mean_flatness = float(np.mean(flatness))
        except Exception as e:
            logger.error("Audio integrity check failed: %s", e)
            return {"is_flagged": False, "needs_secondary_verification": False, "reason": "check_failed"}

        suspicious = pitch_std < self.pitch_variance_threshold or mean_flatness > self.spectral_flatness_threshold

        return {
            "is_flagged": suspicious,
            # E-01: flagged audio ALWAYS goes to secondary verification,
            # never auto-excluded/scored down on this signal alone.
            "needs_secondary_verification": suspicious,
            "reason": "low_pitch_variance_or_high_spectral_flatness" if suspicious else None,
            "pitch_std": pitch_std,
            "spectral_flatness": mean_flatness,
        }

    def check_text(self, was_pasted: bool, user_id: Optional[str] = None) -> Dict[str, any]:
        """E-03: accessibility-exempt users skip paste flagging entirely."""
        if was_pasted and user_id in self.accessibility_exempt_users:
            return {"is_flagged": False, "excluded_from_scoring": False, "reason": "accessibility_exempt"}
        if was_pasted:
            return {"is_flagged": True, "excluded_from_scoring": True, "reason": "clipboard_paste_detected"}
        return {"is_flagged": False, "excluded_from_scoring": False, "reason": None}

    def record_flag_and_check_repeat(self, user_id: str) -> Dict[str, any]:
        """E-02: 3+ flags -> restrict user's sessions from contributing to score."""
        self._flag_counts[user_id] = self._flag_counts.get(user_id, 0) + 1
        count = self._flag_counts[user_id]
        restrict = count >= self.repeated_flag_threshold
        if restrict:
            logger.warning("User '%s' hit repeat-gaming threshold (%d flags) — restricting.", user_id, count)
        return {"flag_count": count, "restrict_user": restrict}

    def resolve(self, audio_check: Dict[str, any], text_check: Dict[str, any]) -> Dict[str, any]:
        """
        Combines both checks. Acceptance criteria: flagged sessions must
        NEVER silently boost the score — this only ever excludes or
        requests re-verification, never scores up.
        """
        any_flagged = audio_check.get("is_flagged", False) or text_check.get("is_flagged", False)
        exclude_from_scoring = text_check.get("excluded_from_scoring", False)
        needs_secondary = audio_check.get("needs_secondary_verification", False)

        return {
            "score_normally": not any_flagged,
            "exclude_from_scoring": exclude_from_scoring,
            "needs_secondary_verification": needs_secondary,
            "audio_reason": audio_check.get("reason"),
            "text_reason": text_check.get("reason"),
        }
