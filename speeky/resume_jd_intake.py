"""
FEATURE: Resume/CV & Job-Description Intake  (US-39 support layer)

SCOPE NOTE — read this first: a teammate owns the actual "ground questioning"
logic (US-39 step 3: AI generates tailored questions referencing resume/JD
details). This file deliberately does NOT generate interview questions. It
owns everything AROUND that step:
  - Resume upload (PDF/DOCX) + text extraction                (Happy Path 1-2)
  - JD paste + cleanup                                          (Happy Path 1-2)
  - Sensitive-data redaction before anything reaches an LLM      (E-03)
  - Resume-JD relevance/mismatch detection                       (E-02, detection only)
  - All upload/parsing failure handling                          (E-01, E-04)
  - Multiple saved resumes + version confirmation                (E-05)
  - Overly-long JD truncation                                    (E-06)

HANDOFF CONTRACT for the teammate building question generation: call
GET /resume-jd-intake/resumes/{resume_id} and GET /resume-jd-intake/jds/{jd_id}
to get back ALREADY-REDACTED resume text and ALREADY-TRUNCATED JD text, plus
GET /resume-jd-intake/mismatch-check for the E-02 signal. Never read raw
uploaded files directly — always go through these endpoints, since that's
where redaction happens. Sensitive data must never reach the LLM context,
per this story's acceptance criteria.

File is organized top-to-bottom as: models -> constants -> service
functions -> FastAPI router. Import `router` from this file into app/main.py.
"""
from __future__ import annotations
import io
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.core.store import store
from app.core.exceptions import SessionNotFoundError, InvalidSubmissionError

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx as python_docx
except ImportError:
    python_docx = None

# ===========================================================================
# MODELS
# ===========================================================================

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
    user_id: str
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


# ===========================================================================
# CONSTANTS
# ===========================================================================

RESUME_NS = "resume_jd_resumes"
JD_NS = "resume_jd_jds"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # E-04: 5MB size limit
MIN_EXTRACTED_WORDS = 20  # below this, treat as scanned/unparsable (E-01)
JD_TRUNCATE_WORD_LIMIT = 600  # E-06

# E-03: sensitive-data patterns. Deliberately conservative regexes — false
# positives (over-redacting) are far safer here than false negatives.
SENSITIVE_PATTERNS = {
    "phone_number": re.compile(r"(\+?\d{1,3}[\s-]?)?\(?\d{3,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
    "cnic_or_ssn": re.compile(r"\b\d{3,5}-\d{6,7}-\d{1}\b|\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
}
ADDRESS_LINE_MARKERS = ["address:", "street", "apt.", "apartment", "zip code", "postal code"]

# E-06: JD sections we KEEP; everything else (benefits, legal boilerplate,
# "about us") gets dropped during truncation.
JD_KEEP_SECTION_HEADERS = ["responsibilities", "requirements", "qualifications", "what you'll do", "what we're looking for"]
JD_DROP_SECTION_HEADERS = ["benefits", "perks", "about us", "equal opportunity", "legal", "compensation", "how to apply"]

# Small static skill/keyword vocabulary for a crude but dependency-free
# resume-vs-JD overlap check (E-02). Teammate's AI question generator can
# do a smarter version later — this is just the detection signal.
SKILL_KEYWORDS = [
    "python", "java", "javascript", "sql", "aws", "azure", "gcp", "docker", "kubernetes",
    "react", "node", "django", "flask", "fastapi", "devops", "ci/cd", "terraform", "ansible",
    "machine learning", "data analysis", "excel", "power bi", "tableau", "sales", "marketing",
    "customer service", "barista", "coffee", "retail", "accounting", "finance", "hr",
    "recruiting", "project management", "agile", "scrum", "linux", "networking", "security",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ===========================================================================
# SERVICE FUNCTIONS — extraction & redaction
# ===========================================================================

def _extract_pdf_text(file_bytes: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf not installed — run: pip install pypdf")
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    if python_docx is None:
        raise RuntimeError("python-docx not installed — run: pip install python-docx")
    doc = python_docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def _redact_sensitive_data(text: str) -> tuple:
    """E-03: strips phone/CNIC/SSN/email and address-labeled lines before
    anything reaches an LLM. Returns (redacted_text, list_of_types_redacted)."""
    redacted_types = []
    result = text

    for label, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(result):
            redacted_types.append(label)
            result = pattern.sub("[REDACTED]", result)

    lines = result.split("\n")
    cleaned_lines = []
    address_found = False
    for line in lines:
        if any(marker in line.lower() for marker in ADDRESS_LINE_MARKERS):
            address_found = True
            continue
        cleaned_lines.append(line)
    if address_found:
        redacted_types.append("address")

    return "\n".join(cleaned_lines), redacted_types


def _truncate_jd(text: str) -> tuple:
    """E-06: keeps Responsibilities/Requirements-type sections, drops
    benefits/legal/about-us boilerplate. Falls back to a flat word-count
    truncation if no recognizable section headers are found."""
    original_word_count = len(text.split())
    lines = text.split("\n")

    keep_mode = None  # None = undecided, True = keep, False = drop
    kept_lines = []
    found_any_header = False

    for line in lines:
        lowered = line.strip().lower()
        if any(h in lowered for h in JD_KEEP_SECTION_HEADERS):
            keep_mode = True
            found_any_header = True
            kept_lines.append(line)
            continue
        if any(h in lowered for h in JD_DROP_SECTION_HEADERS):
            keep_mode = False
            found_any_header = True
            continue
        if keep_mode is not False:
            kept_lines.append(line)

    if found_any_header:
        cleaned = "\n".join(kept_lines).strip()
    else:
        # No headers detected at all — flat truncate as a fallback
        words = text.split()
        cleaned = " ".join(words[:JD_TRUNCATE_WORD_LIMIT])

    cleaned_word_count = len(cleaned.split())
    truncated = cleaned_word_count < original_word_count
    if not found_any_header and cleaned_word_count > JD_TRUNCATE_WORD_LIMIT:
        cleaned = " ".join(cleaned.split()[:JD_TRUNCATE_WORD_LIMIT])
        cleaned_word_count = JD_TRUNCATE_WORD_LIMIT
        truncated = True

    return cleaned, truncated, original_word_count, cleaned_word_count


def _extract_keywords(text: str) -> List[str]:
    lowered = text.lower()
    return sorted({kw for kw in SKILL_KEYWORDS if kw in lowered})


# ===========================================================================
# SERVICE FUNCTIONS — endpoints logic
# ===========================================================================

def upload_resume(user_id: str, filename: str, file_bytes: bytes) -> ResumeUploadResponse:
    now = _now()
    resume_id = _new_id("resume")

    # E-04: size limit / corruption handling — never blocks the session entirely
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        record = {
            "resume_id": resume_id, "user_id": user_id, "filename": filename,
            "parse_status": ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE,
            "extracted_text": "", "redacted_fields": [], "uploaded_at": now,
        }
        store.create(RESUME_NS, resume_id, record)
        return ResumeUploadResponse(
            resume_id=resume_id, user_id=user_id, filename=filename,
            parse_status=ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE, redacted_fields=[],
            extracted_word_count=0, fallback_to_generic=True,
            warning=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)}MB limit. Proceeding with a generic interview instead.",
            uploaded_at=now, last_modified_label=f"{filename} — upload failed",
        )

    try:
        if filename.lower().endswith(".pdf"):
            raw_text = _extract_pdf_text(file_bytes)
        elif filename.lower().endswith(".docx"):
            raw_text = _extract_docx_text(file_bytes)
        else:
            raise ValueError("Unsupported file type — only PDF and DOCX are accepted.")
    except Exception:
        # E-04: corrupted/unreadable file — don't block the session
        record = {
            "resume_id": resume_id, "user_id": user_id, "filename": filename,
            "parse_status": ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE,
            "extracted_text": "", "redacted_fields": [], "uploaded_at": now,
        }
        store.create(RESUME_NS, resume_id, record)
        return ResumeUploadResponse(
            resume_id=resume_id, user_id=user_id, filename=filename,
            parse_status=ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE, redacted_fields=[],
            extracted_word_count=0, fallback_to_generic=True,
            warning="This file couldn't be read (corrupted or unsupported). Proceeding with a generic interview instead.",
            uploaded_at=now, last_modified_label=f"{filename} — upload failed",
        )

    word_count = len(raw_text.split())

    # E-01: image-only scanned PDF -> no extractable text -> generic fallback
    if word_count < MIN_EXTRACTED_WORDS:
        record = {
            "resume_id": resume_id, "user_id": user_id, "filename": filename,
            "parse_status": ParseStatus.FAILED_SCANNED_OR_EMPTY,
            "extracted_text": "", "redacted_fields": [], "uploaded_at": now,
        }
        store.create(RESUME_NS, resume_id, record)
        return ResumeUploadResponse(
            resume_id=resume_id, user_id=user_id, filename=filename,
            parse_status=ParseStatus.FAILED_SCANNED_OR_EMPTY, redacted_fields=[],
            extracted_word_count=word_count, fallback_to_generic=True,
            warning="No readable text found (likely a scanned image). Falling back to the standard question bank — you can paste key experience manually instead.",
            uploaded_at=now, last_modified_label=f"{filename} — text extraction failed",
        )

    # E-03: redact sensitive data BEFORE storing / before anything touches an LLM
    redacted_text, redacted_fields = _redact_sensitive_data(raw_text)

    record = {
        "resume_id": resume_id, "user_id": user_id, "filename": filename,
        "parse_status": ParseStatus.SUCCESS,
        "extracted_text": redacted_text, "redacted_fields": redacted_fields,
        "uploaded_at": now,
    }
    store.create(RESUME_NS, resume_id, record)

    return ResumeUploadResponse(
        resume_id=resume_id, user_id=user_id, filename=filename,
        parse_status=ParseStatus.SUCCESS, redacted_fields=redacted_fields,
        extracted_word_count=len(redacted_text.split()), fallback_to_generic=False,
        warning=(f"Redacted: {', '.join(redacted_fields)}." if redacted_fields else None),
        uploaded_at=now, last_modified_label=f"{filename} — uploaded {now.strftime('%b %d, %Y')}",
    )


def list_resumes(user_id: str) -> List[ResumeSummary]:
    """E-05: lets the frontend show a confirmation step (filename + date)
    before the session starts, when a user has multiple saved resumes."""
    all_resumes = [r for r in store.list_values(RESUME_NS) if r["user_id"] == user_id]
    return [
        ResumeSummary(
            resume_id=r["resume_id"], filename=r["filename"], parse_status=r["parse_status"],
            uploaded_at=r["uploaded_at"], last_modified_label=f"{r['filename']} — {r['uploaded_at'].strftime('%b %d, %Y')}",
        )
        for r in sorted(all_resumes, key=lambda x: x["uploaded_at"], reverse=True)
    ]


def get_resume_detail(resume_id: str) -> ResumeDetailResponse:
    r = store.get(RESUME_NS, resume_id)
    if r is None:
        raise SessionNotFoundError(f"Resume {resume_id} not found")
    return ResumeDetailResponse(
        resume_id=r["resume_id"], filename=r["filename"], parse_status=r["parse_status"],
        extracted_text=r["extracted_text"], redacted_fields=r["redacted_fields"],
    )


def submit_jd(req: PasteJDRequest) -> JDIntakeResponse:
    if not req.jd_text.strip():
        raise InvalidSubmissionError("jd_text cannot be empty")

    cleaned, truncated, orig_wc, cleaned_wc = _truncate_jd(req.jd_text)
    jd_id = _new_id("jd")
    store.create(JD_NS, jd_id, {
        "jd_id": jd_id, "user_id": req.user_id, "cleaned_text": cleaned,
        "truncated": truncated, "created_at": _now(),
    })
    return JDIntakeResponse(
        jd_id=jd_id, truncated=truncated,
        original_word_count=orig_wc, cleaned_word_count=cleaned_wc,
        warning="Trimmed to the Responsibilities/Requirements section." if truncated else None,
    )


def get_jd_detail(jd_id: str) -> JDDetailResponse:
    j = store.get(JD_NS, jd_id)
    if j is None:
        raise SessionNotFoundError(f"JD {jd_id} not found")
    return JDDetailResponse(jd_id=j["jd_id"], cleaned_text=j["cleaned_text"], truncated=j["truncated"])


def check_mismatch(req: MismatchCheckRequest) -> MismatchCheckResponse:
    """E-02: detection only — flags mismatch for the teammate's question
    generator to pivot on. Does not generate any questions itself."""
    resume = store.get(RESUME_NS, req.resume_id)
    jd = store.get(JD_NS, req.jd_id)
    if resume is None:
        raise SessionNotFoundError(f"Resume {req.resume_id} not found")
    if jd is None:
        raise SessionNotFoundError(f"JD {req.jd_id} not found")

    resume_keywords = _extract_keywords(resume.get("extracted_text", ""))
    jd_keywords = _extract_keywords(jd["cleaned_text"])

    if not jd_keywords:
        return MismatchCheckResponse(
            mismatch_detected=False, overlap_score=1.0,
            resume_keywords_found=resume_keywords, jd_keywords_found=jd_keywords,
            note="No recognizable skill keywords found in the JD — mismatch check skipped.",
        )

    overlap = set(resume_keywords) & set(jd_keywords)
    overlap_score = len(overlap) / len(jd_keywords)
    mismatch = overlap_score < 0.2

    return MismatchCheckResponse(
        mismatch_detected=mismatch, overlap_score=round(overlap_score, 2),
        resume_keywords_found=resume_keywords, jd_keywords_found=jd_keywords,
        note=(
            "Low overlap between resume and JD — question generator should pivot toward transferable skills."
            if mismatch else "Reasonable overlap between resume and JD skills."
        ),
    )


# ===========================================================================
# ROUTER
# ===========================================================================

router = APIRouter(prefix="/resume-jd-intake", tags=["Resume/JD Intake"])


@router.post("/resumes", response_model=ResumeUploadResponse, status_code=201)
async def api_upload_resume(user_id: str = Form(...), file: UploadFile = File(...)):
    file_bytes = await file.read()
    return upload_resume(user_id, file.filename, file_bytes)


@router.get("/resumes", response_model=List[ResumeSummary])
def api_list_resumes(user_id: str):
    return list_resumes(user_id)


@router.get("/resumes/{resume_id}", response_model=ResumeDetailResponse)
def api_get_resume(resume_id: str):
    return get_resume_detail(resume_id)


@router.post("/jds", response_model=JDIntakeResponse, status_code=201)
def api_submit_jd(req: PasteJDRequest):
    return submit_jd(req)


@router.get("/jds/{jd_id}", response_model=JDDetailResponse)
def api_get_jd(jd_id: str):
    return get_jd_detail(jd_id)


@router.post("/mismatch-check", response_model=MismatchCheckResponse)
def api_check_mismatch(req: MismatchCheckRequest):
    return check_mismatch(req)


# ===========================================================================
# STANDALONE RUNNER
#   uvicorn app.features.resume_jd_intake:app --reload --port 8004
# ===========================================================================

from fastapi import FastAPI
from app.core.exceptions import install_error_handlers

app = FastAPI(title="Speeky - Resume/JD Intake")
install_error_handlers(app)
app.include_router(router)
