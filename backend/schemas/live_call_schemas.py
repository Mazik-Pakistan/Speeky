from typing import Literal

from pydantic import BaseModel

LiveCallFeature = Literal["conversation", "interview_coach", "scenario", "coaching"]


class LiveCallTokenRequestSchema(BaseModel):
    feature: LiveCallFeature
    session_id: str


class LiveCallTokenResponseSchema(BaseModel):
    token: str
    url: str
    room_name: str
