from typing import Optional
from fastapi import APIRouter, Depends, Query

from middlewares.auth_middleware import require_auth
from schemas.progress_dashboard_schemas import (
    ActivateFreezeRequest,
    DisputeScoreRequest,
    MakeupDrillRequest,
    PracticeSessionLogRequest,
    ProgressReportRequest,
    StreakAppealRequest,
)
from services import progress_dashboard_service
from services.progress_dashboard_service import get_overview, get_progress_dashboard

router = APIRouter()


# ── Full time-series dashboard (PDG-US-10/14) ─────────────────────────────────
router.add_api_route("/progress", get_progress_dashboard, methods=["GET"])
# Flat legacy payload the Vocabulary Growth panel reads — deliberately a different
# shape, not an alias of /progress.
router.add_api_route("/overview", get_overview, methods=["GET"])


# ── Piece 1: Streak Freeze & Vacation Mode ────────────────────────────────────
async def get_streak_endpoint(user_id: str = Depends(require_auth)):
    return await progress_dashboard_service.get_streak_info(user_id)


async def activate_freeze_endpoint(
    payload: ActivateFreezeRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.activate_freeze(payload, user_id)


async def log_practice_endpoint(
    payload: PracticeSessionLogRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.log_practice_session(payload, user_id)


async def makeup_drill_endpoint(
    payload: MakeupDrillRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.perform_makeup_drill(payload, user_id)


# ── Piece 2: Confidence Methodology & Dispute ─────────────────────────────────
async def confidence_breakdown_endpoint(user_id: str = Depends(require_auth)):
    return await progress_dashboard_service.get_confidence_breakdown(user_id)


async def session_detail_endpoint(
    session_id: str, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.get_session_detail(session_id, user_id)


async def dispute_score_endpoint(
    payload: DisputeScoreRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.dispute_session_score(payload, user_id)


# ── Piece 3: Badge Catalog & Locked Preview ──────────────────────────────────
async def get_badges_endpoint(user_id: str = Depends(require_auth)):
    return await progress_dashboard_service.get_badge_catalog(user_id)


# ── Piece 4: Progress Report Export ──────────────────────────────────────────
async def export_report_endpoint(
    payload: ProgressReportRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.generate_progress_report(payload, user_id)


# ── Piece 5: Streak Restore Appeal ───────────────────────────────────────────
async def submit_appeal_endpoint(
    payload: StreakAppealRequest, user_id: str = Depends(require_auth)
):
    return await progress_dashboard_service.submit_streak_appeal(payload, user_id)


# ── Piece 6: Historical Data Retention & Chart Performance ───────────────────
async def get_history_endpoint(
    time_range: str = Query(default="month"),
    user_id: str = Depends(require_auth),
):
    return await progress_dashboard_service.get_historical_data(time_range, user_id)


async def expand_history_endpoint(
    period_label: str = Query(...),
    user_id: str = Depends(require_auth),
):
    return await progress_dashboard_service.expand_period_data(period_label, user_id)


# Register routes matching existing backend router registration conventions
router.add_api_route("/streak", get_streak_endpoint, methods=["GET"])
router.add_api_route("/streak/freeze", activate_freeze_endpoint, methods=["POST"])
router.add_api_route("/streak/practice", log_practice_endpoint, methods=["POST"])
router.add_api_route("/streak/makeup", makeup_drill_endpoint, methods=["POST"])

router.add_api_route("/confidence/breakdown", confidence_breakdown_endpoint, methods=["GET"])
router.add_api_route("/confidence/session/{session_id}", session_detail_endpoint, methods=["GET"])
router.add_api_route("/confidence/dispute", dispute_score_endpoint, methods=["POST"])

router.add_api_route("/badges", get_badges_endpoint, methods=["GET"])
router.add_api_route("/report/export", export_report_endpoint, methods=["POST"])
router.add_api_route("/appeal", submit_appeal_endpoint, methods=["POST"])

router.add_api_route("/history", get_history_endpoint, methods=["GET"])
router.add_api_route("/history/expand", expand_history_endpoint, methods=["GET"])
