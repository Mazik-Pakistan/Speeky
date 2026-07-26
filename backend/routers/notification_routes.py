from fastapi import APIRouter

from services.notification_service import (
    ack_pending_inapp,
    get_pending_inapp,
    get_preferences,
    update_preferences,
)

router = APIRouter()

router.add_api_route("/preferences", get_preferences, methods=["GET"])
router.add_api_route("/preferences", update_preferences, methods=["PATCH"])
router.add_api_route("/pending", get_pending_inapp, methods=["GET"])
router.add_api_route("/pending/ack", ack_pending_inapp, methods=["POST"])
