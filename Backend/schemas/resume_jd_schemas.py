from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ParseStatus(str, Enum):
    SUCCESS = "success"
    FAILED_SCANNED_OR_EMPTY = "failed_scanned_or_empty"  # E-01
    FAILED_CORRUPT_OR_TOO_LARGE = "failed_corrupt_or_too_large"  # E-04


class ResumeUploadResponse(BaseModel):
    resume_id: str
    user_id: str
    filename: str
    parse_status: ParseStatus
    redacted_fields: List[str] = Field(default_factory=list)
    extracted_word_count: int
    fallback_to_generic: bool = False  # E-01/E-04: caller should use generic question bank
    warning: Optional[str] = None
    uploaded_at: datetime
    last_modified_label: str  # E-05: shown in the confirmation step


class ResumeSummary(BaseModel):
    resume_id: str
    filename: str
    parse_status: ParseStatus
    uploaded_at: datetime
    last_modified_label: str


class ResumeDetailResponse(BaseModel):
    resume_id: str
    filename: str
    parse_status: ParseStatus
    extracted_text: str  # already redacted — safe to hand to an LLM
    redacted_fields: List[str]


class PasteJDRequest(BaseModel):
    jd_text: str


class JDIntakeResponse(BaseModel):
    jd_id: str
    truncated: bool  # E-06
    original_word_count: int
    cleaned_word_count: int
    warning: Optional[str] = None


class JDDetailResponse(BaseModel):
    jd_id: str
    cleaned_text: str
    truncated: bool


class MismatchCheckRequest(BaseModel):
    resume_id: str
    jd_id: str


class MismatchCheckResponse(BaseModel):
    mismatch_detected: bool  # E-02
    overlap_score: float  # 0-1, rough keyword overlap
    resume_keywords_found: List[str]
    jd_keywords_found: List[str]
    note: str
