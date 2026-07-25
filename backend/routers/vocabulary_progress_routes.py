from fastapi import APIRouter

from services.vocabulary_progress_service import get_drill_down, get_word_detail

router = APIRouter()

router.add_api_route("/drill-down", get_drill_down, methods=["GET"])
router.add_api_route("/words/{word}", get_word_detail, methods=["GET"])
