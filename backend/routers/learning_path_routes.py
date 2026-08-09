from fastapi import APIRouter, Depends, Query

from middlewares.auth_middleware import require_auth
from schemas.learning_path_schemas import (
    AdminLockRequest,
    AdminPathCreateRequest,
    ManualUnlockOverrideRequest,
    MilestoneEvaluateRequest,
    ModulePauseRequest,
    ModuleResumeRequest,
    PathResetRequest,
    PathSwitchRequest,
)
from services import learning_path_service

router = APIRouter()


# ── Piece 1: Recommendation ───────────────────────────────────────────────────
async def get_recommendation_endpoint(user_id: str = Depends(require_auth)):
    return await learning_path_service.get_personalized_recommendation(user_id)


# ── Piece 2: Path Switching ──────────────────────────────────────────────────
async def switch_path_endpoint(
    payload: PathSwitchRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.switch_learning_path(user_id, payload)


# ── Piece 3: Milestone & Achievement Tracking ─────────────────────────────────
async def evaluate_milestone_endpoint(
    payload: MilestoneEvaluateRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.evaluate_milestone_completion(user_id, payload)


# ── Piece 4: Learning Path Reset ─────────────────────────────────────────────
async def reset_path_endpoint(
    payload: PathResetRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.reset_learning_path(user_id, payload)


# ── Piece 5: Admin Authoring & Locking ───────────────────────────────────────
async def admin_save_path_endpoint(
    payload: AdminPathCreateRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.admin_save_path(user_id, payload)


async def admin_publish_path_endpoint(
    path_id: str, user_id: str = Depends(require_auth)
):
    return await learning_path_service.admin_publish_path(user_id, path_id)


async def admin_delete_module_endpoint(
    module_id: str, user_id: str = Depends(require_auth)
):
    return await learning_path_service.admin_delete_module(user_id, module_id)


async def admin_acquire_lock_endpoint(
    payload: AdminLockRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.admin_acquire_lock(payload)


# ── Piece 6: Pause & Resume Progress Persistence ─────────────────────────────
async def pause_module_endpoint(
    payload: ModulePauseRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.pause_module_session(user_id, payload)


async def resume_module_endpoint(
    payload: ModuleResumeRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.resume_module_session(user_id, payload)


# ── Piece 7: Prerequisite Unlocking & Overrides ─────────────────────────────
async def check_module_access_endpoint(
    path_id: str, module_id: str, user_id: str = Depends(require_auth)
):
    return await learning_path_service.check_module_access(user_id, path_id, module_id)


async def manual_unlock_override_endpoint(
    payload: ManualUnlockOverrideRequest, user_id: str = Depends(require_auth)
):
    return await learning_path_service.set_manual_unlock_override(
        payload.target_user_id, payload.path_id, payload.unlock_all, payload.module_ids
    )


# ── Piece 8: Completion & Certification Summary ──────────────────────────────
async def completion_check_endpoint(
    path_id: str, user_id: str = Depends(require_auth)
):
    return await learning_path_service.check_path_completion(user_id, path_id)


async def certification_summary_endpoint(
    path_id: str, user_id: str = Depends(require_auth)
):
    return await learning_path_service.get_path_certification_summary(user_id, path_id)


# Register endpoints matching existing router conventions
router.add_api_route("/recommendation", get_recommendation_endpoint, methods=["GET"])
router.add_api_route("/switch", switch_path_endpoint, methods=["POST"])
router.add_api_route("/milestone/evaluate", evaluate_milestone_endpoint, methods=["POST"])
router.add_api_route("/reset", reset_path_endpoint, methods=["POST"])

router.add_api_route("/admin/paths", admin_save_path_endpoint, methods=["POST"])
router.add_api_route("/admin/paths/{path_id}/publish", admin_publish_path_endpoint, methods=["POST"])
router.add_api_route("/admin/modules/{module_id}", admin_delete_module_endpoint, methods=["DELETE"])
router.add_api_route("/admin/lock", admin_acquire_lock_endpoint, methods=["POST"])

router.add_api_route("/module/pause", pause_module_endpoint, methods=["POST"])
router.add_api_route("/module/resume", resume_module_endpoint, methods=["POST"])

router.add_api_route("/paths/{path_id}/modules/{module_id}/access", check_module_access_endpoint, methods=["GET"])
router.add_api_route("/admin/override-unlock", manual_unlock_override_endpoint, methods=["POST"])

router.add_api_route("/paths/{path_id}/completion-check", completion_check_endpoint, methods=["GET"])
router.add_api_route("/paths/{path_id}/certification", certification_summary_endpoint, methods=["GET"])
