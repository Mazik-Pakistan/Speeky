from typing import List, Optional

from pydantic import BaseModel, Field


class AssessmentAudioSchema(BaseModel):
    """Optional audio-derived signal for a spoken assessment answer (AUDIO pipeline).

    When present, the response is scored through the audio pipeline (fluency +
    pronunciation) instead of the text pipeline. Same shape as coaching's audio features
    — produced upstream by the STT/VAD agent. `text_data` still carries the transcript.
    """

    duration_seconds: float = 0.0
    word_timings: List[dict] = Field(default_factory=list)
    speech_rate: Optional[float] = None
    pause_count: Optional[int] = None
    mean_pause_duration: Optional[float] = None
    filled_pauses: Optional[int] = None
    avg_db: Optional[float] = None
    pronunciation_score: Optional[float] = None


class SubmitResponseSchema(BaseModel):
    text_data: str = Field(min_length=1)
    clipboard_detected: bool = False
    audio_features: Optional[AssessmentAudioSchema] = None
