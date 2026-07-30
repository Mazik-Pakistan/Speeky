"""Resume/JD Intake (US-39) ported service — extraction/redaction/truncation/mismatch."""

import pytest

from services import resume_jd_service as svc
from schemas.resume_jd_schemas import ParseStatus
from utils.feature_errors import InvalidSubmissionError, SessionNotFoundError

U = "user_1"


def _resume_txt() -> bytes:
    return (
        "Jane Doe\nSoftware Engineer\n"
        "Email: jane.doe@example.com  Phone: +1 415-555-1234\n"
        "Address: 22 Baker Street, Apt. 4\n"
        "Experienced Python and FastAPI developer with AWS and Docker. "
        "Built data analysis pipelines and led agile teams for five years across fintech."
    ).encode()


async def test_upload_redacts_pii_and_succeeds():  # E-03
    r = await svc._upload_resume(U, "cv.txt", _resume_txt())
    assert r.parse_status == ParseStatus.SUCCESS
    assert "email" in r.redacted_fields and "phone_number" in r.redacted_fields
    assert "address" in r.redacted_fields
    detail = await svc._get_resume_detail(U, r.resume_id)
    assert "jane.doe@example.com" not in detail.extracted_text
    assert "[REDACTED]" in detail.extracted_text


async def test_oversized_upload_falls_back():  # E-04
    big = b"x " * (svc.MAX_UPLOAD_BYTES)  # exceeds 5MB
    r = await svc._upload_resume(U, "big.txt", big)
    assert r.parse_status == ParseStatus.FAILED_CORRUPT_OR_TOO_LARGE
    assert r.fallback_to_generic is True


async def test_too_short_is_scanned_fallback():  # E-01
    r = await svc._upload_resume(U, "scan.txt", b"only three words")
    assert r.parse_status == ParseStatus.FAILED_SCANNED_OR_EMPTY
    assert r.fallback_to_generic is True


async def test_resume_ownership_enforced():
    r = await svc._upload_resume(U, "cv.txt", _resume_txt())
    with pytest.raises(SessionNotFoundError):
        await svc._get_resume_detail("someone_else", r.resume_id)


async def test_jd_truncation_drops_boilerplate():  # E-06
    jd = (
        "Responsibilities\nBuild APIs in Python and Django. Own the backend.\n"
        "Requirements\nSQL, AWS, Docker experience.\n"
        "Benefits\nFree coffee, gym, unlimited PTO.\n"
        "About us\nWe are a great company founded long ago."
    )
    resp = await svc._submit_jd(U, jd)
    detail = await svc._get_jd_detail(U, resp.jd_id)
    assert "Free coffee" not in detail.cleaned_text
    assert "Django" in detail.cleaned_text
    assert resp.truncated is True


async def test_empty_jd_rejected():
    with pytest.raises(InvalidSubmissionError):
        await svc._submit_jd(U, "   ")


async def test_mismatch_detection_low_overlap():  # E-02
    r = await svc._upload_resume(U, "cv.txt", _resume_txt())  # python/aws/docker/fastapi...
    jd = await svc._submit_jd(U, "Requirements\nBarista and coffee and retail and customer service experience.")
    res = await svc._check_mismatch(U, r.resume_id, jd.jd_id)
    assert res.mismatch_detected is True
    assert res.overlap_score < 0.2
