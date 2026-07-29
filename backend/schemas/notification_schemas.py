from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

NotificationCadence = Literal["off", "remind_if_not_practiced", "always"]

_HHMM_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class UpdatePreferencesRequest(BaseModel):
    quiet_hours_start: str = Field(pattern=_HHMM_PATTERN, description="24h 'HH:MM' local time")
    quiet_hours_end: str = Field(pattern=_HHMM_PATTERN, description="24h 'HH:MM' local time")
    cadence: NotificationCadence
    device_id: Optional[str] = Field(None, description="Which device made this change — stored for traceability, not for scoping (prefs are account-level, E-04)")


class PreferencesResponse(BaseModel):
    user_id: str
    quiet_hours_start: str
    quiet_hours_end: str
    cadence: NotificationCadence
    updated_at: datetime
    device_id: Optional[str] = None


class PendingInAppItem(BaseModel):
    id: str
    type: str
    message: str
    created_at: datetime


class PendingInAppResponse(BaseModel):
    items: List[PendingInAppItem]


class AckPendingRequest(BaseModel):
    item_id: str
