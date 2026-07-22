from typing import Optional

from pydantic import BaseModel, Field, model_validator

from schemas.coaching_schemas import AudioFeaturesSchema


class StartConversationSchema(BaseModel):
    """Provide either a preset topic_key OR a free-text custom_topic — never both."""

    topic_key: Optional[str] = Field(None, description="daily_life|travel|technology|education|work")
    custom_topic: Optional[str] = Field(None, min_length=3, max_length=200)
    level_override: Optional[str] = Field(None, description="beginner|intermediate|advanced")
    show_corrections: bool = False  # opt-in, off by default

    @model_validator(mode="after")
    def exactly_one_topic_source(self):
        if bool(self.topic_key) == bool(self.custom_topic):
            raise ValueError("Provide exactly one of topic_key or custom_topic")
        return self


class SendMessageSchema(BaseModel):
    text: str = ""
    input_mode: str = "text"  # "text" | "audio" 
    audio_features: Optional[AudioFeaturesSchema] = None
    show_corrections: Optional[bool] = None  # per-message override of the session default

    @model_validator(mode="after")
    def has_content(self):
        transcript = self.text or (self.audio_features.transcript if self.audio_features else "")
        if not transcript.strip():
            raise ValueError("text or audio_features.transcript is required")
        return self


class MemoryOptOutSchema(BaseModel):
    enabled: bool


class TTSRequestSchema(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    length_scale: float = Field(1.0, ge=0.5, le=2.0)
