from fastapi import APIRouter

from services.practice_time_service import get_trophy_case, ping_practice_time

router = APIRouter()

router.add_api_route("/ping", ping_practice_time, methods=["POST"])
router.add_api_route("/trophies", get_trophy_case, methods=["GET"])
