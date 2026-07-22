from fastapi import APIRouter

from services.session_memory_service import (
    get_interruption_status,
    get_memory_profile,
    get_personalized_opening,
    log_interruption,
    record_session,
    resume_session,
)

router = APIRouter()

# Session & Memory Handling
router.add_api_route("/interruptions", log_interruption, methods=["POST"], status_code=201)
router.add_api_route("/interruptions/{session_id}/status", get_interruption_status, methods=["GET"])
router.add_api_route("/resume", resume_session, methods=["POST"])
router.add_api_route("/profile/record-session", record_session, methods=["POST"], status_code=201)
router.add_api_route("/profile", get_memory_profile, methods=["GET"])
router.add_api_route("/profile/personalized-opening", get_personalized_opening, methods=["GET"])
