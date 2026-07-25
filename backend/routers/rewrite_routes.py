from fastapi import APIRouter

from services.rewrite_service import (
    explain_rewrite,
    generate_rewrite,
    score_rewrite,
)

router = APIRouter()

# Post-Session Actionable Script — Rewrite trio
router.add_api_route("/generate", generate_rewrite, methods=["POST"])  # US-158
router.add_api_route("/score", score_rewrite, methods=["POST"])        # US-156
router.add_api_route("/explain", explain_rewrite, methods=["POST"])    # US-159
