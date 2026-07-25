from fastapi import APIRouter

from services.overuse_service import dismiss_nudge, record_heartbeat

router = APIRouter()

router.add_api_route("/heartbeat", record_heartbeat, methods=["POST"])
router.add_api_route("/dismiss", dismiss_nudge, methods=["POST"])
