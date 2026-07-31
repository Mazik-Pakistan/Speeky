from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Which feature session this heartbeat belongs to, if any")


class OveruseNudgePayload(BaseModel):
    type: str = "break_suggested"
    message: str
    is_followup: bool = False


class HeartbeatResponse(BaseModel):
    continuous_minutes: float
    nudge: Optional[OveruseNudgePayload] = None


class DismissNudgeRequest(BaseModel):
    pass


class DismissNudgeResponse(BaseModel):
    dismissed: bool
    dismissed_at: datetime
