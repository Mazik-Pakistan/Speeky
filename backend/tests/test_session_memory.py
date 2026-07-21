"""Session & Memory Handling (US-28) ported service."""

from datetime import timedelta

import pytest

from schemas.session_memory_schemas import (
    InterruptionStatus,
    InterruptionType,
    LogInterruptionRequest,
    RecordSessionRequest,
)
from services import session_memory_service as svc

U = "user_1"


def _log_req(sess="sess_1", partial=None):
    return LogInterruptionRequest(
        session_id=sess, session_type="interview_coach",
        interruption_type=InterruptionType.PHONE_CALL, partial_answer_text=partial,
    )


async def test_interruption_count_and_status():  # E-03
    await svc._log_interruption(U, _log_req())
    r2 = await svc._log_interruption(U, _log_req())
    assert r2.interruption_count_this_session == 2
    status = await svc._get_interruption_status(U, "sess_1")
    assert status.has_active_interruption is True
    assert status.interruption_count_this_session == 2


async def test_resume_restores_partial_answer():  # E-01/E-05
    await svc._log_interruption(U, _log_req(partial="I was saying that..."))
    resp = await svc._resume_session(U, "sess_1")
    assert resp.status == InterruptionStatus.RESUMED
    assert resp.partial_answer_text == "I was saying that..."


async def test_resume_stale_after_threshold(monkeypatch):  # E-02
    await svc._log_interruption(U, _log_req())
    real_now = svc._now()
    monkeypatch.setattr(svc, "_now", lambda: real_now + timedelta(minutes=svc.STALE_RESUME_THRESHOLD_MINUTES + 5))
    resp = await svc._resume_session(U, "sess_1")
    assert resp.stale is True
    assert resp.status == InterruptionStatus.STALE


async def test_resume_without_interruption_404():
    from utils.feature_errors import SessionNotFoundError
    with pytest.raises(SessionNotFoundError):
        await svc._resume_session(U, "never_interrupted")


async def test_interruptions_are_user_scoped():
    await svc._log_interruption(U, _log_req())
    other = await svc._get_interruption_status("other_user", "sess_1")
    assert other.has_active_interruption is False
    assert other.interruption_count_this_session == 0


async def test_memory_profile_recurring_weakness():
    for i in range(2):
        await svc._record_session(U, RecordSessionRequest(
            session_id=f"s{i}", session_type="interview_coach",
            flags_seen=["rambling"], topic_or_mode="SWE interview", overall_score=60))
    profile = await svc._build_memory_profile(U)
    assert profile.sessions_recorded == 2
    assert "rambling" in profile.recurring_weaknesses  # appeared in 2+ sessions


async def test_memory_profile_strength_from_high_score():
    await svc._record_session(U, RecordSessionRequest(
        session_id="s1", session_type="interview_coach",
        flags_seen=[], topic_or_mode="Case interview", overall_score=90))
    profile = await svc._build_memory_profile(U)
    assert "Case interview" in profile.recurring_strengths


async def test_personalized_opening_no_history():  # E-04
    resp = await svc._get_personalized_opening("new_user")
    assert resp.has_history is False
    assert "first practice session" in resp.opening_message


async def test_personalized_opening_with_history_uses_ai_stub():
    await svc._record_session(U, RecordSessionRequest(
        session_id="s1", session_type="interview_coach",
        flags_seen=["rambling", "rambling"], topic_or_mode="SWE", overall_score=50))
    resp = await svc._get_personalized_opening(U)
    assert resp.has_history is True
    assert resp.opening_message  # offline ai_client stub returns a non-empty line
