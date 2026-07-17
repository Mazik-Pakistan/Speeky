"""
Speeky - A self-hosted, offline, AI-assisted English language practice pipeline.

This package provides modules for speech recognition, pronunciation analysis,
grammar correction, fluency assessment, and conversational practice using
British English standards.
"""

import logging

__version__ = "0.1.0"
__author__ = "Speeky Project"

try:
    from .vad import VoiceActivityDetector
    from .asr import AutomaticSpeechRecognition
    from .alignment import WordAligner
    from .pronunciation import PronunciationScorer
    from .grammar import GrammarCorrector
    from .fluency import FluencyAnalyzer
    from .response import ConversationEngine
    from .tts import TextToSpeech
except ImportError as e:
    # These pull in heavy optional ML deps (torch, spacy, faster-whisper, silero-vad).
    # Baseline Assessment's text-mode flow doesn't need them, so degrade gracefully
    # rather than blocking `import speeky` entirely, mirroring pipeline.py's own fallback.
    logging.getLogger(__name__).warning(f"Optional audio/NLP component unavailable: {e}")
    VoiceActivityDetector = None
    AutomaticSpeechRecognition = None
    WordAligner = None
    PronunciationScorer = None
    GrammarCorrector = None
    FluencyAnalyzer = None
    ConversationEngine = None
    TextToSpeech = None

from .pipeline import SpeekyPipeline
from .confidence import ConfidenceScoreEngine, ScoringWeights, SessionScore, ConfidenceGrammarAnalyzer
from .storage import InMemoryStorage, LearningLevel, AssessmentStatus
from .assessment import InitialCommunicationAssessment
from .results import ResultsSummaryView
from .gating import FeatureAccessGating, FeatureAccessLevel, GatedFeature, BasicFeature
from .reassessment import PeriodicReAssessment

__all__ = [
    "VoiceActivityDetector",
    "AutomaticSpeechRecognition",
    "WordAligner",
    "PronunciationScorer",
    "GrammarCorrector",
    "FluencyAnalyzer",
    "ConfidenceGrammarAnalyzer",
    "ConversationEngine",
    "TextToSpeech",
    "SpeekyPipeline",
    "ConfidenceScoreEngine",
    "ScoringWeights",
    "SessionScore",
    "InMemoryStorage",
    "LearningLevel",
    "AssessmentStatus",
    "InitialCommunicationAssessment",
    "ResultsSummaryView",
    "FeatureAccessGating",
    "FeatureAccessLevel",
    "GatedFeature",
    "BasicFeature",
    "PeriodicReAssessment",
]
