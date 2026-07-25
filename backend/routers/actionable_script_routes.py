from typing import Optional
from fastapi import APIRouter, Depends, Query

from middlewares.auth_middleware import require_auth
from schemas.actionable_script_schemas import (
    DeleteScriptRequest,
    ProcessScriptRequest,
    PronunciationHandoffRequest,
    SaveScriptRequest,
)
from services import actionable_script_service

router = APIRouter()


async def process_script_endpoint(payload: ProcessScriptRequest, user_id: str = Depends(require_auth)):
    return await actionable_script_service.process_script(payload)


async def save_script_endpoint(payload: SaveScriptRequest, user_id: str = Depends(require_auth)):
    return await actionable_script_service.save_script(payload, user_id)


async def list_scripts_endpoint(user_id: str = Depends(require_auth)):
    return await actionable_script_service.list_user_scripts(user_id)


async def delete_script_endpoint(
    script_id: str,
    confirmed: bool = Query(default=False),
    user_id: str = Depends(require_auth),
):
    return await actionable_script_service.delete_user_script(script_id, confirmed, user_id)


async def push_to_pronunciation_endpoint(
    payload: PronunciationHandoffRequest,
    user_id: str = Depends(require_auth),
):
    return await actionable_script_service.push_to_pronunciation(payload, user_id)


# Register routes matching existing backend patterns
router.add_api_route("/process", process_script_endpoint, methods=["POST"])
router.add_api_route("/save", save_script_endpoint, methods=["POST"])
router.add_api_route("/library", list_scripts_endpoint, methods=["GET"])
router.add_api_route("/library/{script_id}", delete_script_endpoint, methods=["DELETE"])
router.add_api_route("/push-to-pronunciation", push_to_pronunciation_endpoint, methods=["POST"])
