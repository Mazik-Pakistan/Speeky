"""
Resume/CV & Job-Description Intake (US-39 support layer).

Ported from the incoming speeky/resume_jd_intake.py into backend conventions:
persistence via lib.kv_store, auth via require_auth (user_id comes from the token, not
the request body), errors via utils.feature_errors. The extraction/redaction/truncation
logic is unchanged — it's the security-critical part (E-03 redaction before anything
reaches an LLM). Ownership is enforced: a user can only read their own resumes/JDs.
"""

import io
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, File, UploadFile

from lib import kv_store, pii
from middlewares.auth_middleware import require_auth
from schemas.resume_jd_schemas import (
    JDDetailResponse,
    JDIntakeResponse,
    MismatchCheckRequest,
    MismatchCheckResponse,
    ParseStatus,
    PasteJDRequest,
    ResumeDetailResponse,
    ResumeSummary,
    ResumeUploadResponse,
)
from utils.feature_errors import InvalidSubmissionError, SessionNotFoundError

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx as python_docx
except ImportError:
    python_docx = None

RESUME_NS = "resume_jd_resumes"
JD_NS = "resume_jd_jds"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # E-04: 5MB size limit
MIN_EXTRACTED_WORDS = 20  # below this, treat as scanned/unparsable (E-01)
JD_TRUNCATE_WORD_LIMIT = 600  # E-06

JD_KEEP_SECTION_HEADERS = ["responsibilities", "requirements", "qualifications", "what you'll do", "what we're looking for"]
JD_DROP_SECTION_HEADERS = ["benefits", "perks", "about us", "equal opportunity", "legal", "compensation", "how to apply"]

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


# ── extraction & redaction (pure) ─────────────────────────────────────────────
def _extract_pdf_text(file_bytes: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf not installed")
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    if python_docx is None:
        raise RuntimeError("python-docx not installed")
    doc = python_docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def _truncate_jd(text: str):
    """E-06: keep Responsibilities/Requirements sections, drop benefits/legal/about-us."""
    original_word_count = len(text.split())
    keep_mode = None
    kept_lines = []
    found_any_header = False
    for line in text.split("\n"):
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
        cleaned = " ".join(text.split()[:JD_TRUNCATE_WORD_LIMIT])

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


# ── service logic ─────────────────────────────────────────────────────────────
async def _upload_resume(user_id: str, filename: str, file_bytes: bytes) -> ResumeUploadResponse:
    now = _now()
    resume_id = _new_id("resume")

    async def _store_failure(status: ParseStatus, warning: str, label_suffix: str) -> ResumeUploadResponse:
        await kv_store.store.create(RESUME_NS, resume_id, {
            "resume_id": resume_id, "user_id": user_id, "filename": filename,
            "parse_status": status, "extracted_text": "", "redacted_fields": [], "uploaded_at": now,
        })
        return ResumeUploadResponse(
            resume_id=resume_id, user_id=user_id, filename=filename, parse_status=status,
            redacted_fields=[], extracted_word_count=0, fallback_to_generic=True,
            warning=warning, uploaded_at=now, last_modified_label=f"{filename} — {label_suffix}",
        )

    # E-04: size limit
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return await _store_failure(
            ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE,
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)}MB limit. Proceeding with a generic interview instead.",
            "upload failed",
        )

    try:
        if filename.lower().endswith(".pdf"):
            raw_text = _extract_pdf_text(file_bytes)
        elif filename.lower().endswith(".docx"):
            raw_text = _extract_docx_text(file_bytes)
        elif filename.lower().endswith(".txt"):
            raw_text = file_bytes.decode("utf-8", errors="ignore")
        else:
            raise ValueError("Unsupported file type — only PDF, DOCX, TXT are accepted.")
    except Exception:
        # E-04: corrupted/unreadable — don't block the session
        return await _store_failure(
            ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE,
            "This file couldn't be read (corrupted or unsupported). Proceeding with a generic interview instead.",
            "upload failed",
        )

    if len(raw_text.split()) < MIN_EXTRACTED_WORDS:
        # E-01: scanned/image-only -> generic fallback
        return await _store_failure(
            ParseStatus.FAILED_SCANNED_OR_EMPTY,
            "No readable text found (likely a scanned image). Falling back to the standard question bank.",
            "text extraction failed",
        )

    # E-03: redact BEFORE storing / before anything touches an LLM
    redacted_text, redacted_fields = pii.redact(raw_text)
    await kv_store.store.create(RESUME_NS, resume_id, {
        "resume_id": resume_id, "user_id": user_id, "filename": filename,
        "parse_status": ParseStatus.SUCCESS, "extracted_text": redacted_text,
        "redacted_fields": redacted_fields, "uploaded_at": now,
    })
    return ResumeUploadResponse(
        resume_id=resume_id, user_id=user_id, filename=filename, parse_status=ParseStatus.SUCCESS,
        redacted_fields=redacted_fields, extracted_word_count=len(redacted_text.split()),
        fallback_to_generic=False,
        warning=(f"Redacted: {', '.join(redacted_fields)}." if redacted_fields else None),
        uploaded_at=now, last_modified_label=f"{filename} — uploaded {now.strftime('%b %d, %Y')}",
    )


async def _list_resumes(user_id: str) -> List[ResumeSummary]:
    mine = [r for r in await kv_store.store.list_values(RESUME_NS) if r["user_id"] == user_id]
    return [
        ResumeSummary(
            resume_id=r["resume_id"], filename=r["filename"], parse_status=r["parse_status"],
            uploaded_at=r["uploaded_at"],
            last_modified_label=f"{r['filename']} — {r['uploaded_at'].strftime('%b %d, %Y')}",
        )
        for r in sorted(mine, key=lambda x: x["uploaded_at"], reverse=True)
    ]


async def _get_resume_detail(user_id: str, resume_id: str) -> ResumeDetailResponse:
    r = await kv_store.store.get(RESUME_NS, resume_id)
    if r is None or r["user_id"] != user_id:
        raise SessionNotFoundError(f"Resume {resume_id} not found")
    return ResumeDetailResponse(
        resume_id=r["resume_id"], filename=r["filename"], parse_status=r["parse_status"],
        extracted_text=r["extracted_text"], redacted_fields=r["redacted_fields"],
    )


async def _submit_jd(user_id: str, jd_text: str) -> JDIntakeResponse:
    if not jd_text.strip():
        raise InvalidSubmissionError("jd_text cannot be empty")
    cleaned, truncated, orig_wc, cleaned_wc = _truncate_jd(jd_text)
    jd_id = _new_id("jd")
    await kv_store.store.create(JD_NS, jd_id, {
        "jd_id": jd_id, "user_id": user_id, "cleaned_text": cleaned,
        "truncated": truncated, "created_at": _now(),
    })
    return JDIntakeResponse(
        jd_id=jd_id, truncated=truncated, original_word_count=orig_wc, cleaned_word_count=cleaned_wc,
        warning="Trimmed to the Responsibilities/Requirements section." if truncated else None,
    )


async def _get_jd_detail(user_id: str, jd_id: str) -> JDDetailResponse:
    j = await kv_store.store.get(JD_NS, jd_id)
    if j is None or j["user_id"] != user_id:
        raise SessionNotFoundError(f"JD {jd_id} not found")
    return JDDetailResponse(jd_id=j["jd_id"], cleaned_text=j["cleaned_text"], truncated=j["truncated"])


async def _check_mismatch(user_id: str, resume_id: str, jd_id: str) -> MismatchCheckResponse:
    """E-02: detection only — flags mismatch for the question generator to pivot on."""
    resume = await kv_store.store.get(RESUME_NS, resume_id)
    jd = await kv_store.store.get(JD_NS, jd_id)
    if resume is None or resume["user_id"] != user_id:
        raise SessionNotFoundError(f"Resume {resume_id} not found")
    if jd is None or jd["user_id"] != user_id:
        raise SessionNotFoundError(f"JD {jd_id} not found")

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
        note=("Low overlap between resume and JD — question generator should pivot toward transferable skills."
              if mismatch else "Reasonable overlap between resume and JD skills."),
    )


# ── controllers (auth-gated) ──────────────────────────────────────────────────
async def upload_resume(user_id: str = Depends(require_auth), file: UploadFile = File(...)):
    return await _upload_resume(user_id, file.filename, await file.read())


async def list_resumes(user_id: str = Depends(require_auth)):
    return await _list_resumes(user_id)


async def get_resume_detail(resume_id: str, user_id: str = Depends(require_auth)):
    return await _get_resume_detail(user_id, resume_id)


async def submit_jd(payload: PasteJDRequest, user_id: str = Depends(require_auth)):
    return await _submit_jd(user_id, payload.jd_text)


async def get_jd_detail(jd_id: str, user_id: str = Depends(require_auth)):
    return await _get_jd_detail(user_id, jd_id)


async def check_mismatch(payload: MismatchCheckRequest, user_id: str = Depends(require_auth)):
    return await _check_mismatch(user_id, payload.resume_id, payload.jd_id)
