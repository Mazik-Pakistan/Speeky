from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ChallengeStatus(str, Enum):
    QUALIFIED = "qualified"
    QUALIFIED_RETROACTIVE = "qualified_retroactive"
    INCOMPLETE_LOW_ENGAGEMENT = "incomplete_low_engagement"
    INCOMPLETE_DURATION = "incomplete_duration"
    REJECTED_NON_INTERACTIVE = "rejected_non_interactive"


class DisputeStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    RESOLVED_GENUINE = "resolved_genuine"
    RESOLVED_DENIED = "resolved_denied"


class StartChallengeRequest(BaseModel):
    device_id: Optional[str] = None


class StartChallengeResponse(BaseModel):
    session_id: str
    user_id: str
    started_at: datetime


class ChallengeTurnResponse(BaseModel):
    session_id: str
    turn_count: int


class CompleteChallengeRequest(BaseModel):
    session_id: str


class CompleteChallengeResponse(BaseModel):
    session_id: str
    status: ChallengeStatus
    current_streak: int
    longest_streak: int
    quality_score: float
    pattern: Optional[str] = None
    message: Optional[str] = None
    milestone_days: Optional[int] = None
    milestone_message: Optional[str] = None
    overuse_nudge: Optional["OveruseNudgePayload"] = None


class DisputeSessionRequest(BaseModel):
    session_id: str


class DisputeSessionResponse(BaseModel):
    session_id: str
    dispute_status: DisputeStatus
    message: str


class ReviewSessionRequest(BaseModel):
    session_id: str
    confirmed_genuine: bool


class ReviewSessionResponse(BaseModel):
    session_id: str
    dispute_status: DisputeStatus
    status: ChallengeStatus
    current_streak: int
    longest_streak: int
    message: str


class StreakResponse(BaseModel):
    user_id: str
    current_streak: int
    longest_streak: int
    qualified_dates: List[str]


# Deferred import to avoid a circular dependency (overuse schemas don't need daily
# challenge schemas), resolved via forward ref above.
from schemas.overuse_schemas import OveruseNudgePayload  # noqa: E402

CompleteChallengeResponse.model_rebuild()
