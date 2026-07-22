from fastapi import APIRouter

from services.progress_dashboard_service import get_overview

router = APIRouter()

router.add_api_route("/overview", get_overview, methods=["GET"])
