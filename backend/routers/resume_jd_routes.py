from fastapi import APIRouter

from services.resume_jd_service import (
    check_mismatch,
    get_jd_detail,
    get_resume_detail,
    list_resumes,
    submit_jd,
    upload_resume,
)

router = APIRouter()

# Resume/CV & Job-Description Intake
router.add_api_route("/resumes", upload_resume, methods=["POST"], status_code=201)
router.add_api_route("/resumes", list_resumes, methods=["GET"])
router.add_api_route("/resumes/{resume_id}", get_resume_detail, methods=["GET"])
router.add_api_route("/jds", submit_jd, methods=["POST"], status_code=201)
router.add_api_route("/jds/{jd_id}", get_jd_detail, methods=["GET"])
router.add_api_route("/mismatch-check", check_mismatch, methods=["POST"])
