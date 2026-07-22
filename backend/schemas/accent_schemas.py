from typing import List, Optional

from pydantic import BaseModel


class TargetPassageSchema(BaseModel):
    passage_id: str
    difficulty: str
    title: str
    text: str


class WeakPointSchema(BaseModel):
    issue: str
    detail: str


class AccentAssessmentResultSchema(BaseModel):
    assessment_id: str
    passage_id: str
    status: str
    transcript: Optional[str] = None
    pronunciation_score: Optional[float] = None
    stress_score: Optional[float] = None
    rhythm_score: Optional[float] = None
    intonation_score: Optional[float] = None
    clarity_score: Optional[float] = None
    weak_points: List[WeakPointSchema] = []


class AccentProfileSchema(BaseModel):
    profile_id: str
    source_assessment_id: str
    pronunciation_score: float
    stress_score: float
    rhythm_score: float
    intonation_score: float
    clarity_score: float
    weak_points: List[WeakPointSchema]
    exercises: List[str]
    created_at: str


class RecordingRejectedSchema(BaseModel):
    """Returned (422) instead of scores when the passage reading fails a quality check."""

    status: str = "rejected"
    reason: str
    message: str
