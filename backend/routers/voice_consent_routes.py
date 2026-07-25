from fastapi import APIRouter

from services.voice_consent_service import (
    delete_voice_samples,
    get_voice_consent,
    update_voice_consent,
)

router = APIRouter()

router.add_api_route("", get_voice_consent, methods=["GET"])
router.add_api_route("", update_voice_consent, methods=["PATCH"])
router.add_api_route("/voice-samples", delete_voice_samples, methods=["DELETE"])