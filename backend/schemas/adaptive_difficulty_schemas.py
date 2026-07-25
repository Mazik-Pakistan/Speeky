from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Request / Response Schemas for Adaptive Difficulty Progression ─────────

class ScoredAttemptRequest(BaseModel):
    metric_name: str = Field(
        ...,
        description="Target metric/phoneme/pattern name (e.g. 'th_sound', 'rising_intonation')",
        examples=["th_sound", "rising_intonation"],
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Accuracy/performance score between 0.0 and 100.0",
        examples=[88.5],
    )
    drill_item: str = Field(
        ...,
        min_length=1,
        description="The specific phrase or sentence used during the attempt",
        examples=["Thirty-three thankful turtles"],
    )


class ScoredAttemptResponse(BaseModel):
    user_id: str
    metric_name: str
    score: float
    drill_item: str
    previous_level: int
    current_level: int
    escalated: bool
    regressed: bool
    consecutive_mastery_count: int
    distinct_drill_items_count: int
    message: str


class GenerateDrillRequest(BaseModel):
    metric_name: str = Field(..., description="Target metric name (e.g. 'th_sound')")
    level: Optional[int] = Field(
        default=None,
        ge=1,
        description="Explicit difficulty level override (if omitted, uses user's current level for metric)",
    )


class GenerateDrillResponse(BaseModel):
    metric_name: str
    level: int
    drill_phrase: str
    source: str = Field(..., description="'llm' if generated live by Groq, or 'static_fallback' if degraded")
    complexity_notes: str


class EscalationEvent(BaseModel):
    metric_name: str
    event_type: str = Field(..., description="'initial', 'escalation', or 'regression'")
    from_level: int
    to_level: int
    reached_at: str
    trigger_reason: str


class EscalationHistoryResponse(BaseModel):
    metric_name: str
    current_level: int
    history: List[EscalationEvent]


class MetricProgressionState(BaseModel):
    metric_name: str
    current_level: int
    consecutive_mastery_count: int
    recent_drill_items: List[str]
    total_attempts: int
    last_score: Optional[float] = None
    last_attempt_at: Optional[str] = None
