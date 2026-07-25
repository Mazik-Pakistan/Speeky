from typing import Optional

from pydantic import BaseModel, Field

VOICE_CONSENT_POLICY_VERSION = "ACC-US-02-v1"


class VoiceConsentUpdateSchema(BaseModel):
    granted: bool
    policy_version: str = Field(default=VOICE_CONSENT_POLICY_VERSION)
    region: Optional[str] = None


class VoiceConsentPreferenceSchema(BaseModel):
    granted: bool
    policy_version: str
    retention_days: int
    raw_audio_retained: bool
    consented_at: Optional[str] = None
    withdrawn_at: Optional[str] = None
    raw_audio_deleted_at: Optional[str] = None
    region: Optional[str] = None


class VoiceSampleDeletionSchema(BaseModel):
    deleted_audio_samples: int
    raw_audio_retained: bool
    message: str