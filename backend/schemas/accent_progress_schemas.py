from pydantic import BaseModel, Field


class SubmitAccentAssessmentSchema(BaseModel):
    pronunciation_score: float = Field(ge=0, le=100)
    word_stress_score: float = Field(ge=0, le=100)
    intonation_score: float = Field(ge=0, le=100)
    clarity_score: float = Field(ge=0, le=100)
