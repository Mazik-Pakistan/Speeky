from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class InterruptionType(str, Enum):
    PHONE_CALL = "phone_call"
    APP_BACKGROUNDED = "app_backgrounded"
    CONNECTIVITY_DROP = "connectivity_drop"
    MANUAL = "manual"


class InterruptionStatus(str, Enum):
    ACTIVE = "active"      # currently interrupted, awaiting resume
    RESUMED = "resumed"
    STALE = "stale"        # too much time passed, resume not offered


class LogInterruptionRequest(BaseModel):
    session_id: str
    session_type: str = Field(..., description="e.g. 'interview_coach', 'workplace_english'")
    interruption_type: InterruptionType
    partial_answer_text: Optional[str] = Field(
        None, description="E-01: whatever the user had typed/said when interrupted"
    )


class InterruptionResponse(BaseModel):
    interruption_id: str
    session_id: str
    status: InterruptionStatus
    interruption_count_this_session: int
    logged_at: datetime


class ResumeRequest(BaseModel):
    session_id: str


class ResumeResponse(BaseModel):
    session_id: str
    status: InterruptionStatus
    partial_answer_text: Optional[str] = None
    stale: bool = False
    message: str


class InterruptionStatusResponse(BaseModel):
    session_id: str
    has_active_interruption: bool
    interruption_count_this_session: int
    last_interruption_at: Optional[datetime] = None


class RecordSessionRequest(BaseModel):
    session_id: str
    session_type: str
    flags_seen: List[str] = Field(default_factory=list, description="e.g. ['rambling', 'one_word_answer']")
    topic_or_mode: Optional[str] = Field(None, description="e.g. 'standard interview - Software Engineer'")
    overall_score: Optional[int] = None


class MemoryProfile(BaseModel):
    user_id: str
    sessions_recorded: int
    recurring_weaknesses: List[str]
    recurring_strengths: List[str]
    recent_topics: List[str]
    last_updated: datetime


class PersonalizedOpeningResponse(BaseModel):
    user_id: str
    has_history: bool
    opening_message: str
