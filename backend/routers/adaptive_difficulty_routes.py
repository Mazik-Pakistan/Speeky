from typing import Optional
from fastapi import APIRouter, Depends, Query

from middlewares.auth_middleware import require_auth
from schemas.adaptive_difficulty_schemas import (
    EscalationHistoryResponse,
    GenerateDrillRequest,
    GenerateDrillResponse,
    MetricProgressionState,
    ScoredAttemptRequest,
    ScoredAttemptResponse,
)
from services import adaptive_difficulty_service

router = APIRouter()


async def record_attempt_endpoint(
    payload: ScoredAttemptRequest,
    user_id: str = Depends(require_auth),
) -> ScoredAttemptResponse:
    return await adaptive_difficulty_service.record_attempt(payload, user_id)


async def generate_drill_endpoint(
    payload: GenerateDrillRequest,
    user_id: str = Depends(require_auth),
) -> GenerateDrillResponse:
    return await adaptive_difficulty_service.generate_drill(payload, user_id)


async def get_history_endpoint(
    metric_name: str,
    user_id: str = Depends(require_auth),
) -> EscalationHistoryResponse:
    return await adaptive_difficulty_service.get_escalation_history(metric_name, user_id)


async def get_state_endpoint(
    metric_name: str,
    user_id: str = Depends(require_auth),
) -> MetricProgressionState:
    return await adaptive_difficulty_service.get_metric_state(metric_name, user_id)


# Register routes matching existing backend router registration conventions
router.add_api_route("/attempt", record_attempt_endpoint, methods=["POST"])
router.add_api_route("/generate-drill", generate_drill_endpoint, methods=["POST"])
router.add_api_route("/history/{metric_name}", get_history_endpoint, methods=["GET"])
router.add_api_route("/state/{metric_name}", get_state_endpoint, methods=["GET"])
