from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class BaselineScoresSchema(BaseModel):
    structure: float
    grammar: float
    professional_tone: float
    vocabulary: float
    confidence: float
    clarity: float
    completeness: float


class ProcessScriptRequest(BaseModel):
    submission: str = Field(description="The original user spoken or written response text")
    scenario_context: Optional[str] = Field(default=None, description="Optional scenario context e.g. technical interview")
    language: Optional[str] = Field(default="en", description="Language of submission, defaults to 'en'")


class ProcessScriptResponse(BaseModel):
    script_id: str
    baseline_status: str  # "completed", "Insufficient Data", etc.
    baseline_scores: Optional[BaselineScoresSchema] = None
    rewrite_status: str  # "success", "minor_polish", "skipped", "failed"
    polished_rewrite: Optional[str] = None
    rewrite_note: Optional[str] = None
    newly_introduced_words: List[str] = Field(default_factory=list)
    category: str = "General"


class SaveScriptRequest(BaseModel):
    script_id: Optional[str] = None
    original_text: str
    polished_rewrite: str
    category: Optional[str] = None
    baseline_scores: Optional[Dict] = None
    rewrite_status: Optional[str] = "success"


class DeleteScriptRequest(BaseModel):
    confirmed: bool = False


class PronunciationHandoffRequest(BaseModel):
    script_id: Optional[str] = None
    polished_text: str
    category: str = "General"
