"""Interview Coach (US-40/42/43/44/45) ported service."""

import pytest
from pydantic import ValidationError

from schemas.interview_coach_schemas import (
    AnswerRequest,
    InterviewMode,
    Panelist,
    PersonaTone,
    ShareReviewRequest,
    StartSessionRequest,
)
from services import interview_coach_service as svc
from utils.feature_errors import (
    InvalidSubmissionError,
    SessionAlreadyEndedError,
    SessionNotFoundError,
)

U = "user_1"


async def _start(**kw):
    return await svc._start_session(U, StartSessionRequest(**kw))


# ── request validation (US-40 / US-43 caps) ──────────────────────────────────
def test_panel_requires_panelists():
    with pytest.raises(ValidationError):
        StartSessionRequest(mode=InterviewMode.PANEL)


def test_panel_capped_at_three():
    with pytest.raises(ValidationError):
        StartSessionRequest(mode=InterviewMode.PANEL, panelists=[
            Panelist(name=n, focus_area="x") for n in ("a", "b", "c", "d")])


def test_multi_round_capped_at_four():
    with pytest.raises(ValidationError):
        StartSessionRequest(mode=InterviewMode.MULTI_ROUND, rounds=[InterviewMode.STANDARD] * 5)


# ── standard session lifecycle (US-45) ───────────────────────────────────────
async def test_start_standard_session():
    r = await _start(mode=InterviewMode.STANDARD, role_or_major="Software Engineer")
    assert r.session_id
    assert "Software Engineer" in r.opening_question
    assert r.status.value == "active"


async def test_one_word_answer_flagged():  # E-03
    s = await _start(role_or_major="SWE")
    resp = await svc._submit_answer(U, s.session_id, AnswerRequest(answer_text="Yes"))
    assert "one_word_answer" in resp.flags
    assert resp.next_question


async def test_rambling_flagged():  # E-02
    s = await _start(role_or_major="SWE")
    resp = await svc._submit_answer(U, s.session_id, AnswerRequest(
        answer_text="I have a lot to say about this topic and I will keep going on and on.",
        response_duration_seconds=200))
    assert "rambling" in resp.flags


async def test_answer_ownership_enforced():
    s = await _start(role_or_major="SWE")
    with pytest.raises(SessionNotFoundError):
        await svc._submit_answer("intruder", s.session_id, AnswerRequest(answer_text="Hello there friend"))


async def test_end_session_produces_scorecards():
    s = await _start(role_or_major="SWE")
    await svc._submit_answer(U, s.session_id, AnswerRequest(answer_text="A reasonably detailed answer about my background."))
    fb = await svc._end_session(U, s.session_id)
    assert fb.round_scorecards
    assert 0 <= fb.overall_score <= 100
    assert fb.closing_message


async def test_cannot_answer_completed_session():
    s = await _start(role_or_major="SWE")
    await svc._end_session(U, s.session_id)
    with pytest.raises(SessionAlreadyEndedError):
        await svc._submit_answer(U, s.session_id, AnswerRequest(answer_text="late answer here please"))


# ── case study (US-42) ───────────────────────────────────────────────────────
async def test_case_jumped_to_number_triggers_walkback():  # E-01
    s = await _start(mode=InterviewMode.CASE_STUDY, case_type="market_sizing")
    resp = await svc._submit_answer(U, s.session_id, AnswerRequest(answer_text="42"))
    assert "jumped_to_number" in resp.flags
    assert resp.next_question


async def test_case_clarifying_question_locks_constraint():  # E-06
    s = await _start(mode=InterviewMode.CASE_STUDY, case_type="market_sizing")
    resp = await svc._submit_answer(U, s.session_id, AnswerRequest(
        answer_text="How large is the target population in this city?"))
    assert "clarifying_question" in resp.flags
    session = await svc._get_session(s.session_id, U)
    assert session["case_established_constraints"]  # a constraint was improvised + locked


# ── panel (US-40) ─────────────────────────────────────────────────────────────
async def test_panel_starts_with_named_interviewer():
    s = await _start(mode=InterviewMode.PANEL, panelists=[
        Panelist(name="Dana", persona_tone=PersonaTone.FORMAL_PANEL, focus_area="culture fit")])
    assert "Dana" in s.opening_question


# ── multi-round (US-43) ───────────────────────────────────────────────────────
async def test_multi_round_starts_interview_day():
    s = await _start(mode=InterviewMode.MULTI_ROUND,
                     rounds=[InterviewMode.STANDARD, InterviewMode.PANEL])
    assert "Interview Day" in s.opening_question
    assert s.current_round == "standard"


# ── mentor/peer review sharing (US-44) ───────────────────────────────────────
async def test_full_share_requires_content_confirmation():  # E-03
    s = await _start(role_or_major="SWE")
    with pytest.raises(InvalidSubmissionError):
        await svc._share_review(U, s.session_id, ShareReviewRequest(
            recipient_email_or_id="mentor@x.com", access_level="full", content_confirmed=False))


async def test_share_and_comment_flow():
    s = await _start(role_or_major="SWE")
    share = await svc._share_review(U, s.session_id, ShareReviewRequest(recipient_email_or_id="mentor@x.com"))
    c = await svc._add_peer_comment("mentor", share.share_id, "Great structure, work on brevity.")
    listed = await svc._list_peer_comments(share.share_id)
    assert any(x["comment_id"] == c.comment_id for x in listed)


async def test_reported_comment_hidden_and_author_blocked_after_two():  # E-06
    s = await _start(role_or_major="SWE")
    share = await svc._share_review(U, s.session_id, ShareReviewRequest(recipient_email_or_id="m@x.com"))
    for _ in range(2):
        c = await svc._add_peer_comment("troll", share.share_id, "spam comment")
        await svc._report_comment(U, c.comment_id)
    # hidden comments drop out of the list
    assert await svc._list_peer_comments(share.share_id) == []
    # third attempt blocked after two reports
    with pytest.raises(InvalidSubmissionError):
        await svc._add_peer_comment("troll", share.share_id, "one more")


async def test_revoke_only_by_owner():  # E-05
    s = await _start(role_or_major="SWE")
    share = await svc._share_review(U, s.session_id, ShareReviewRequest(recipient_email_or_id="m@x.com"))
    with pytest.raises(SessionNotFoundError):
        await svc._revoke_share("not_owner", share.share_id)
    ok = await svc._revoke_share(U, share.share_id)
    assert ok["revoked"] is True
