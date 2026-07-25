from fastapi import APIRouter

from services.pronunciation_coach_service import (
    check_resumable_session,
    end_session,
    get_session,
    interrupt_session,
    resume_session,
    retry_word,
    start_session,
    submit_attempt,
)

router = APIRouter()

# Pronunciation Coach (GAP-03/04/05) + Retry Loop (US-071) + Session Interruption
# Recovery (GAP-09) — one continuous session.
router.add_api_route("/start", start_session, methods=["POST"], status_code=201)
router.add_api_route("/resume", check_resumable_session, methods=["GET"])
router.add_api_route("/{session_id}/attempt", submit_attempt, methods=["POST"])
router.add_api_route("/{session_id}/retry", retry_word, methods=["POST"])
router.add_api_route("/{session_id}/interrupt", interrupt_session, methods=["POST"])
router.add_api_route("/{session_id}/resume", resume_session, methods=["POST"])
router.add_api_route("/{session_id}/end", end_session, methods=["POST"])
router.add_api_route("/{session_id}", get_session, methods=["GET"])
