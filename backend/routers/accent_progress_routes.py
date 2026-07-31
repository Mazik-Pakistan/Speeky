from fastapi import APIRouter

from services.accent_progress_service import get_progress_matrix, submit_assessment

router = APIRouter()

router.add_api_route("/assessments", submit_assessment, methods=["POST"])
router.add_api_route("/matrix", get_progress_matrix, methods=["GET"])
