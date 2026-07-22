from fastapi import APIRouter

from services.pronunciation_coach_service import get_target_sentence, submit_pronunciation_attempt

router = APIRouter()

# Pronunciation Coach (US-95)
router.add_api_route("/sentences", get_target_sentence, methods=["GET"])
router.add_api_route("/sentences/{sentence_id}/attempts", submit_pronunciation_attempt, methods=["POST"])
