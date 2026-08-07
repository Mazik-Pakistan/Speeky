from typing import Literal

from pydantic import BaseModel

# public_speaking is Q&A-only: the speech itself is a monologue that a live agent would talk
# over, so live_call_service refuses to mint a token until the session reaches "qa_phase".
LiveCallFeature = Literal[
    "conversation", "interview_coach", "scenario", "coaching", "public_speaking"
]


class LiveCallTokenRequestSchema(BaseModel):
    feature: LiveCallFeature
    session_id: str


class LiveCallTokenResponseSchema(BaseModel):
    token: str
    url: str
    room_name: str
