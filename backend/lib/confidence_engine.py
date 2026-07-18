"""
Confidence-first scoring: prioritizes successful communication over strict
grammatical perfection. Stateless — callers reconstruct the engine per
request and replay a user's session history into it (see
services/assessment_service.py), since nothing here is persisted directly.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for confidence score calculation."""

    fluency: float = 50.0
    vocabulary: float = 30.0
    pronunciation: float = 20.0

    def __post_init__(self):
        total = self.fluency + self.vocabulary + self.pronunciation
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Weights must sum to 100%, got {total}%")


@dataclass
class SessionScore:
    """Individual session score data."""

    timestamp: datetime
    fluency_score: float
    vocabulary_score: float
    pronunciation_score: Optional[float] = None
    is_text_only: bool = False
    is_complete: bool = True
    is_outlier: bool = False


class ConfidenceScoreEngine:
    """
    Confidence score calculation and aggregation engine.

    Reconstructed fresh per request and fed a user's completed sessions
    (oldest first) via add_session_score() — see
    services/assessment_service.py's _score_confidence.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        self.session_history: List[SessionScore] = []
        self.current_confidence_score: float = 0.0

    def calculate_session_confidence(self, session_score: SessionScore) -> float:
        """Calculate confidence score for a single session (0-100)."""
        if not session_score.is_complete:
            return 0.0
        if session_score.is_outlier:
            return 0.0

        if session_score.is_text_only or session_score.pronunciation_score is None:
            # Normalize fluency and vocabulary to 100% for text-only sessions.
            total_weight = self.weights.fluency + self.weights.vocabulary
            fluency_weight = (self.weights.fluency / total_weight) * 100
            vocab_weight = (self.weights.vocabulary / total_weight) * 100

            confidence = (session_score.fluency_score * fluency_weight / 100) + (
                session_score.vocabulary_score * vocab_weight / 100
            )
        else:
            confidence = (
                (session_score.fluency_score * self.weights.fluency / 100)
                + (session_score.vocabulary_score * self.weights.vocabulary / 100)
                + (session_score.pronunciation_score * self.weights.pronunciation / 100)
            )

        return round(confidence, 2)

    def detect_outlier(self, session_score: SessionScore, variance_threshold: float = 50.0) -> bool:
        """Flag a session as a statistical outlier vs. recent history."""
        if len(self.session_history) < 3:
            return False

        recent_scores = [s for s in self.session_history[-10:] if s.is_complete and not s.is_outlier]
        if not recent_scores:
            return False

        avg_fluency = sum(s.fluency_score for s in recent_scores) / len(recent_scores)
        avg_vocab = sum(s.vocabulary_score for s in recent_scores) / len(recent_scores)

        fluency_variance = abs(session_score.fluency_score - avg_fluency) / avg_fluency * 100 if avg_fluency else 0.0
        vocab_variance = abs(session_score.vocabulary_score - avg_vocab) / avg_vocab * 100 if avg_vocab else 0.0

        return fluency_variance > variance_threshold or vocab_variance > variance_threshold

    def add_session_score(self, session_score: SessionScore):
        """Add a session score and recalculate the aggregate confidence score."""
        session_score.is_outlier = self.detect_outlier(session_score)
        self.session_history.append(session_score)
        self._recalculate_aggregate_confidence()

    def _recalculate_aggregate_confidence(self):
        """Weighted average of session confidence scores, log-capped for long-term users."""
        complete_sessions = [s for s in self.session_history if s.is_complete and not s.is_outlier]

        if not complete_sessions:
            self.current_confidence_score = 0.0
            return

        session_confidences = [self.calculate_session_confidence(s) for s in complete_sessions]

        if len(session_confidences) > 100:
            import math

            scaling_factor = math.log(100) / math.log(len(session_confidences))
            avg_confidence = sum(session_confidences) / len(session_confidences)
            self.current_confidence_score = min(100.0, avg_confidence * scaling_factor)
        else:
            self.current_confidence_score = sum(session_confidences) / len(session_confidences)

        self.current_confidence_score = round(self.current_confidence_score, 2)

    def get_confidence_score(self) -> float:
        return self.current_confidence_score

    def get_confidence_breakdown(self) -> Dict:
        """Plain-language breakdown of the current confidence score."""
        recent_sessions = self.session_history[-10:] if self.session_history else []

        if not recent_sessions:
            return {
                "current_score": 0.0,
                "explanation": "Complete the Initial Communication Assessment to establish your baseline confidence score.",
                "components": {
                    "fluency": {"weight": self.weights.fluency, "recent_average": 0},
                    "vocabulary": {"weight": self.weights.vocabulary, "recent_average": 0},
                    "pronunciation": {"weight": self.weights.pronunciation, "recent_average": 0},
                },
            }

        complete_recent = [s for s in recent_sessions if s.is_complete and not s.is_outlier]

        avg_fluency = sum(s.fluency_score for s in complete_recent) / len(complete_recent) if complete_recent else 0
        avg_vocab = sum(s.vocabulary_score for s in complete_recent) / len(complete_recent) if complete_recent else 0
        pron_scores = [s.pronunciation_score for s in complete_recent if s.pronunciation_score is not None]
        avg_pron = sum(pron_scores) / len(pron_scores) if pron_scores else None

        if self.current_confidence_score >= 80:
            level = "high"
        elif self.current_confidence_score >= 60:
            level = "moderate"
        else:
            level = "developing"

        explanation = (
            f"Your confidence score reflects your {level} ability to communicate effectively. "
            f"Based on your recent sessions, you're performing "
            f"{'strongly' if level == 'high' else 'well' if level == 'moderate' else 'and building foundational skills'}. "
            f"Keep practicing to improve your fluency and vocabulary usage."
        )

        return {
            "current_score": self.current_confidence_score,
            "explanation": explanation,
            "components": {
                "fluency": {
                    "weight": self.weights.fluency,
                    "recent_average": round(avg_fluency, 1),
                    "description": "Flow and naturalness of speech",
                },
                "vocabulary": {
                    "weight": self.weights.vocabulary,
                    "recent_average": round(avg_vocab, 1),
                    "description": "Word choice and variety",
                },
                "pronunciation": {
                    "weight": self.weights.pronunciation,
                    "recent_average": round(avg_pron, 1) if avg_pron is not None else None,
                    "description": "Clarity and accuracy of pronunciation",
                },
            },
        }
