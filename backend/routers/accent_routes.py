from fastapi import APIRouter

from services.accent_assessment_service import get_target_passage, submit_passage_assessment
from services.accent_profile_service import get_exercises, get_profile

router = APIRouter()

# Accent Assessment -- Rhythm & Stress Patterns (US-93)
router.add_api_route("/passages", get_target_passage, methods=["GET"])
router.add_api_route("/passages/{passage_id}/assessments", submit_passage_assessment, methods=["POST"])

# Accent Profile & Improvement (US-89)
router.add_api_route("/profile", get_profile, methods=["GET"])
router.add_api_route("/profile/exercises", get_exercises, methods=["GET"])
