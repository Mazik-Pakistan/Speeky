from typing import List, Optional

from pydantic import BaseModel


class TargetSentenceSchema(BaseModel):
    sentence_id: str
    difficulty: str
    text: str
    focus_sounds: List[str]


class WordResultSchema(BaseModel):
    word: str
    target_index: int
    status: str  # correct | mispronounced | stress_error | skipped
    confidence: Optional[float] = None


class PronunciationResultSchema(BaseModel):
    attempt_id: str
    sentence_id: str
    target_text: str
    transcript: str
    overall_score: float
    word_results: List[WordResultSchema]
    attempt_count: int
    background_voice_detected: bool
    disfluency_detected: bool
    accent_profile: Optional[str] = None


class RecordingRejectedSchema(BaseModel):
    """Returned (422) instead of a score when the recording fails a quality check."""

    status: str = "rejected"
    reason: str
    message: str
