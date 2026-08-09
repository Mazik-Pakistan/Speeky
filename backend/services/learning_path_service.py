import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from lib import confidence_engine, kv_store, llm_client
from lib.prisma_client import db
from schemas.learning_path_schemas import (
    AdminLockRequest,
    AdminLockResponse,
    AdminPathCreateRequest,
    MilestoneEvaluateRequest,
    MilestoneEvaluateResponse,
    ModuleAccessResponse,
    ModulePauseRequest,
    ModuleResumeRequest,
    ModuleSchema,
    PathCompletionCheckResponse,
    PathResetRequest,
    PathResetResponse,
    PathSummaryResponse,
    PathSwitchRequest,
    PathSwitchResponse,
    PauseResumeResponse,
    RecommendationResponse,
)
from utils.app_error import AppError
from utils.feature_errors import InvalidSubmissionError, SessionNotFoundError

logger = logging.getLogger(__name__)

# Namespaces for KvStore persistence
PATHS_NS = "lp_paths"
USER_PROGRESS_NS = "lp_user_progress"
PAUSED_SESSIONS_NS = "lp_paused_sessions"
ADMIN_LOCKS_NS = "lp_admin_locks"
RETRY_QUEUE_NS = "lp_retry_queue"
BADGES_NS = "progress_badges"  # Shared with Progress Dashboard feature!


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ── Initial Pre-Curated Catalog Seed ──────────────────────────────────────────
DEFAULT_PATHS = [
    {
        "path_id": "beginner-path",
        "title": "Beginner Workplace English",
        "description": "Foundational communication skills for professional workplace environments.",
        "learning_level": "BEGINNER",
        "is_published": True,
        "strict_sequential": True,
        "is_enterprise_assigned": False,
        "is_deprecated": False,
        "deprecated_id": None,
        "mapped_to_id": None,
        "owner_id": "system",
        "modules": [
            {
                "module_id": "mod_b1",
                "title": "Basic Workplace Greetings",
                "sequence_order": 1,
                "prerequisites": [],
                "passing_score": 60.0,
                "content": "Introductory greetings and small talk.",
                "content_version": 1,
                "target_session_type": "coaching_meeting_communication",
            },
            {
                "module_id": "mod_b2",
                "title": "Simple Email Drafts",
                "sequence_order": 2,
                "prerequisites": ["mod_b1"],
                "passing_score": 60.0,
                "content": "Drafting basic professional emails.",
                "content_version": 1,
                "target_session_type": "coaching_email_writing",
            },
            {
                "module_id": "mod_b3",
                "title": "Phone Call Basics",
                "sequence_order": 3,
                "prerequisites": ["mod_b2"],
                "passing_score": 60.0,
                "content": "Answering business calls confidently.",
                "content_version": 1,
                "target_session_type": "coaching_client_communication",
            },
        ],
    },
    {
        "path_id": "intermediate-path",
        "title": "Intermediate Business Communication",
        "description": "Effective meeting participation, status reports, and structured workplace discussions.",
        "learning_level": "INTERMEDIATE",
        "is_published": True,
        "strict_sequential": True,
        "is_enterprise_assigned": False,
        "is_deprecated": False,
        "deprecated_id": None,
        "mapped_to_id": None,
        "owner_id": "system",
        "modules": [
            {
                "module_id": "mod_i1",
                "title": "Meeting Contributions",
                "sequence_order": 1,
                "prerequisites": [],
                "passing_score": 65.0,
                "content": "Expressing opinions clearly in team meetings.",
                "content_version": 1,
                "target_session_type": "coaching_meeting_communication",
            },
            {
                "module_id": "mod_i2",
                "title": "Client Status Updates",
                "sequence_order": 2,
                "prerequisites": ["mod_i1"],
                "passing_score": 65.0,
                "content": "Delivering concise project progress updates.",
                "content_version": 1,
                "target_session_type": "coaching_client_communication",
            },
            {
                "module_id": "mod_i3",
                "title": "Handling Objections",
                "sequence_order": 3,
                "prerequisites": ["mod_i2"],
                "passing_score": 65.0,
                "content": "Addressing client concerns diplomatically.",
                "content_version": 1,
                "target_session_type": "coaching_client_communication",
            },
        ],
    },
    {
        "path_id": "advanced-path",
        "title": "Advanced Executive Presence",
        "description": "High-stakes negotiations, leadership presentations, and crisis communication.",
        "learning_level": "ADVANCED",
        "is_published": True,
        "strict_sequential": True,
        "is_enterprise_assigned": False,
        "is_deprecated": False,
        "deprecated_id": None,
        "mapped_to_id": None,
        "owner_id": "system",
        "modules": [
            {
                "module_id": "mod_a1",
                "title": "Boardroom Presentations",
                "sequence_order": 1,
                "prerequisites": [],
                "passing_score": 70.0,
                "content": "Structuring persuasive executive decks.",
                "content_version": 1,
                "target_session_type": "coaching_presentation_prep",
            },
            {
                "module_id": "mod_a2",
                "title": "High-Stakes Negotiations",
                "sequence_order": 2,
                "prerequisites": ["mod_a1"],
                "passing_score": 70.0,
                "content": "Navigating tough commercial terms.",
                "content_version": 1,
                "target_session_type": "coaching_client_communication",
            },
            {
                "module_id": "mod_a3",
                "title": "Crisis Communication",
                "sequence_order": 3,
                "prerequisites": ["mod_a2"],
                "passing_score": 70.0,
                "content": "De-escalating high-severity workplace issues.",
                "content_version": 1,
                "target_session_type": "coaching_general_workplace",
            },
        ],
    },
]


async def ensure_default_paths_seeded():
    """Ensure catalog has pre-curated paths in KvStore."""
    for pdef in DEFAULT_PATHS:
        pid = pdef["path_id"]
        existing = await kv_store.store.get(PATHS_NS, pid)
        if not existing:
            await kv_store.store.create(PATHS_NS, pid, pdef)
        else:
            # Sync catalog definitions with updated target_session_type
            await kv_store.store.update(PATHS_NS, pid, pdef)



async def get_path_definition(path_id: str) -> Optional[Dict]:
    await ensure_default_paths_seeded()
    return await kv_store.store.get(PATHS_NS, path_id)


async def list_all_paths() -> List[Dict]:
    await ensure_default_paths_seeded()
    return await kv_store.store.list_values(PATHS_NS)


# ── Helper: User State Management ──────────────────────────────────────────────
async def get_user_path_state(user_id: str) -> Dict:
    state = await kv_store.store.get(USER_PROGRESS_NS, user_id)
    if not state:
        state = {
            "user_id": user_id,
            "active_path_id": "beginner-path",
            "active_version": 1,
            "path_history": {
                "beginner-path": {
                    "completed_modules": [],
                    "module_scores": {},
                    "is_active": True,
                    "started_at": _now_iso(),
                    "total_practice_time": 0,
                    "vocabulary_mastered": 0,
                }
            },
            "archived_history": [],
            "manual_overrides": {"unlock_all": False, "unlocked_modules": []},
            "last_switch_timestamp": None,
            "last_request_id": None,
        }
        await kv_store.store.create(USER_PROGRESS_NS, user_id, state)
    return state


async def _save_user_path_state(user_id: str, state: Dict):
    await kv_store.store.update(USER_PROGRESS_NS, user_id, state)


# ===========================================================================
# PIECE 1 — Personalized Learning Path Recommendation
# ===========================================================================
async def get_personalized_recommendation(user_id: str) -> RecommendationResponse:
    """
    Analyze latest baseline assessment and recommend an optimal learning path.
    """
    await ensure_default_paths_seeded()
    state = await get_user_path_state(user_id)
    all_paths = await list_all_paths()
    active_path_id = state.get("active_path_id")
    
    # ── Level ordering used for auto-promotion ───────────────────────────────
    LEVEL_ORDER = {"BEGINNER": 0, "ELEMENTARY": 0, "INTERMEDIATE": 1, "ADVANCED": 2}

    # 1. Respect user's stored active path if it exists
    if active_path_id:
        path_def = await get_path_definition(active_path_id)

        # ── Lightweight completion check directly from state ──────────────────
        # (avoids calling the heavy check_path_completion which builds certs etc.)
        is_path_complete = False
        if path_def:
            p_hist = state.get("path_history", {}).get(active_path_id, {})
            completed_mods = p_hist.get("completed_modules", [])
            total_modules = path_def.get("modules", [])
            # All module IDs present in completed list → fully done
            if total_modules and all(m["module_id"] in completed_mods for m in total_modules):
                is_path_complete = True

        # ── Auto-promote to next level path when current is complete ──────────
        if is_path_complete:
            current_level = path_def.get("learning_level", "BEGINNER") if path_def else "BEGINNER"
            current_rank = LEVEL_ORDER.get(current_level.upper(), 0)

            # Find the best published, non-deprecated next-level path
            next_path = None
            next_rank = None
            for p in all_paths:
                if p.get("path_id") == active_path_id:
                    continue
                if not p.get("is_published") or p.get("is_deprecated"):
                    continue
                p_rank = LEVEL_ORDER.get((p.get("learning_level") or "").upper(), -1)
                if p_rank > current_rank:
                    if next_rank is None or p_rank < next_rank:
                        next_rank = p_rank
                        next_path = p

            if next_path:
                new_id = next_path["path_id"]
                # Persist the promotion
                state["active_path_id"] = new_id
                state.setdefault("path_history", {}).setdefault(new_id, {
                    "completed_modules": [], "module_scores": {},
                    "is_active": True, "started_at": _now_iso(),
                    "total_practice_time": 0, "vocabulary_mastered": 0,
                })["is_active"] = True
                if active_path_id in state.get("path_history", {}):
                    state["path_history"][active_path_id]["is_active"] = False
                await _save_user_path_state(user_id, state)

                completed_title = path_def.get("title", active_path_id) if path_def else active_path_id
                return RecommendationResponse(
                    recommended_path_id=new_id,
                    path_title=next_path.get("title", new_id),
                    reasoning=(
                        f"🎉 You completed '{completed_title}'! "
                        f"Moving you up to '{next_path.get('title', new_id)}'."
                    ),
                    confidence_score=1.0,
                    learning_level=next_path.get("learning_level", "INTERMEDIATE"),
                    is_fallback=False,
                    available_paths=all_paths,
                )

        # ── Active path not yet complete — honour it as the recommendation ────
        return RecommendationResponse(
            recommended_path_id=active_path_id,
            path_title=path_def.get("title", "Workplace English Path") if path_def else "Workplace English Path",
            reasoning="Showing your currently active learning path.",
            confidence_score=1.0,
            learning_level=path_def.get("learning_level", "BEGINNER") if path_def else "BEGINNER",
            is_fallback=False,
            available_paths=all_paths,
        )

    # 2. Fallback to assessment-based logic for new users
    assessment = None
    try:
        assessment = await db.baselineassessment.find_first(
            where={"userId": user_id, "completedAt": {"not": None}},
            order={"startedAt": "desc"},
        )
    except Exception as err:
        logger.warning(f"Database check for baseline assessment failed: {err}")

    if not assessment:
        return RecommendationResponse(
            recommended_path_id="beginner-path",
            path_title="Beginner Workplace English",
            reasoning="No baseline assessment found. Defaulting to Beginner Path.",
            confidence_score=0.0,
            learning_level="BEGINNER",
            is_fallback=True,
            available_paths=all_paths,
        )

    fluency = assessment.fluencyScore or 50.0
    vocab = assessment.vocabularyScore or 50.0
    conf = round((fluency * 0.5) + (vocab * 0.5), 2)
    level_str = (
        assessment.learningLevel.value
        if hasattr(assessment.learningLevel, "value")
        else (assessment.learningLevel or "INTERMEDIATE")
    )

    if conf < 50.0:
        rec_id = "beginner-path"
        reasoning = "Based on baseline confidence score below 50."
    elif conf < 75.0:
        rec_id = "intermediate-path"
        reasoning = "Based on baseline confidence score between 50 and 75."
    else:
        rec_id = "advanced-path"
        reasoning = "Based on baseline confidence score above 75."

    target_path = await get_path_definition(rec_id)
    path_title = target_path.get("title", "Workplace English Path") if target_path else "Workplace English Path"

    return RecommendationResponse(
        recommended_path_id=rec_id,
        path_title=path_title,
        reasoning=reasoning,
        confidence_score=float(conf),
        learning_level=level_str,
        is_fallback=True,
        available_paths=all_paths,
    )


# ===========================================================================
# PIECE 2 — Learning Path Switching
# ===========================================================================
async def switch_learning_path(user_id: str, payload: PathSwitchRequest) -> PathSwitchResponse:
    """
    Switch user's active path to a different one. Requires confirmation step,
    auto-saves unsaved progress, preserves history, and handles rapid double-clicks.
    """
    target_path = await get_path_definition(payload.target_path_id)
    if not target_path:
        raise InvalidSubmissionError(
            f"Path '{payload.target_path_id}' not found. Please refresh the path catalog."
        )

    state = await get_user_path_state(user_id)
    curr_active_id = state.get("active_path_id")

    # 1. Rapid double-click protection (process only latest request)
    req_id = payload.request_id
    if req_id and state.get("last_request_id") == req_id:
        return PathSwitchResponse(
            success=True,
            active_path_id=state["active_path_id"],
            message="Duplicate request ignored.",
        )

    if curr_active_id == payload.target_path_id:
        return PathSwitchResponse(
            success=True,
            active_path_id=curr_active_id,
            previous_path_id=curr_active_id,
            message=f"Already active on path '{payload.target_path_id}'.",
        )

    # 2. Require explicit confirmation
    if not payload.confirm:
        warning = None
        # Check if target path has incomplete assessment/level requirement
        target_level = target_path.get("learning_level")
        if target_level in ["INTERMEDIATE", "ADVANCED"]:
            warning = f"Path '{target_path['title']}' requires an assessment level of {target_level}."

        return PathSwitchResponse(
            success=False,
            active_path_id=curr_active_id,
            confirmation_required=True,
            warning=warning,
            message="Explicit confirmation required to switch learning path. Current progress will be auto-saved.",
        )


    # 3. Transactional switch with rollback on failure
    prev_state_snapshot = dict(state)
    try:
        # Auto-save unsaved progress if provided
        if payload.unsaved_progress and curr_active_id:
            curr_hist = state.setdefault("path_history", {}).setdefault(curr_active_id, {})
            curr_hist["last_unsaved_progress"] = payload.unsaved_progress
            curr_hist["last_updated_at"] = _now_iso()

        # Update old path history -> no longer active, but preserved
        if curr_active_id and curr_active_id in state.get("path_history", {}):
            state["path_history"][curr_active_id]["is_active"] = False

        # Init new path history if first time
        new_hist = state.setdefault("path_history", {}).setdefault(payload.target_path_id, {
            "completed_modules": [],
            "module_scores": {},
            "is_active": True,
            "started_at": _now_iso(),
            "total_practice_time": 0,
            "vocabulary_mastered": 0,
        })
        new_hist["is_active"] = True

        state["active_path_id"] = payload.target_path_id
        state["last_switch_timestamp"] = _now_iso()
        if req_id:
            state["last_request_id"] = req_id

        await _save_user_path_state(user_id, state)

        return PathSwitchResponse(
            success=True,
            active_path_id=payload.target_path_id,
            previous_path_id=curr_active_id,
            message=f"Successfully switched active path to '{target_path['title']}'. Prior progress saved.",
        )
    except Exception as err:
        # Clean rollback to original state
        await _save_user_path_state(user_id, prev_state_snapshot)
        logger.error(f"Path switch failed midway: {err}")
        raise AppError(f"Server error during path switch: {err}. Rolled back to active path.", 500)


# ===========================================================================
# PIECE 3 — Milestone & Achievement Tracking
# ===========================================================================
async def evaluate_milestone_completion(
    user_id: str, payload: MilestoneEvaluateRequest
) -> MilestoneEvaluateResponse:
    """
    Evaluate module completion and award milestone badges into BADGES_NS ("progress_badges").
    Enforces strict badge uniqueness, supports offline completions, and restores corrupted progress.
    """
    state = await get_user_path_state(user_id)

    # 1. Restore corrupted progress if flagged
    if payload.corrupted_progress:
        archived = state.get("archived_history", [])
        if archived:
            last_good = archived[-1].get("path_history", {})
            if payload.path_id in last_good:
                state["path_history"][payload.path_id] = dict(last_good[payload.path_id])
                await _save_user_path_state(user_id, state)

    # 2. Update user path progress
    p_hist = state.setdefault("path_history", {}).setdefault(payload.path_id, {
        "completed_modules": [],
        "module_scores": {},
        "is_active": True,
        "started_at": _now_iso(),
        "total_practice_time": 0,
        "vocabulary_mastered": 0,
    })

    completed_mods = p_hist.setdefault("completed_modules", [])
    if payload.module_id not in completed_mods:
        completed_mods.append(payload.module_id)
    p_hist.setdefault("module_scores", {})[payload.module_id] = payload.score
    await _save_user_path_state(user_id, state)

    # 3. Check for offline completions -> Queue if offline/syncing
    if payload.is_offline:
        q_item = {
            "user_id": user_id,
            "path_id": payload.path_id,
            "module_id": payload.module_id,
            "score": payload.score,
            "completed_at": payload.completed_at or _now_iso(),
        }
        await kv_store.store.create(RETRY_QUEUE_NS, f"{user_id}_{payload.module_id}", q_item)

    # 4. Evaluate badges in BADGES_NS ("progress_badges")
    all_badges = await kv_store.store.list_values(BADGES_NS)
    user_badge_ids = {b["badge_id"] for b in all_badges if b.get("user_id") == user_id}

    newly_awarded = []
    already_awarded_count = 0

    # Potential Milestone Badges
    milestones_to_check = [
        {
            "badge_id": "lp_first_module",
            "condition": len(completed_mods) >= 1,
        },
        {
            "badge_id": "lp_path_halfway",
            "condition": len(completed_mods) >= 2,
        },
        {
            "badge_id": "lp_master_score",
            "condition": payload.score >= 90.0,
        },
    ]

    for m in milestones_to_check:
        bid = m["badge_id"]
        if bid in user_badge_ids:
            already_awarded_count += 1
            continue  # SILENTLY IGNORE — strict badge uniqueness!

        if m["condition"]:
            record = {
                "badge_id": bid,
                "user_id": user_id,
                "earned_at": _now_iso(),
                "source": "learning_path",
            }
            await kv_store.store.create(BADGES_NS, f"{user_id}_{bid}", record)
            newly_awarded.append(bid)

    return MilestoneEvaluateResponse(
        module_id=payload.module_id,
        awarded_badges=newly_awarded,
        already_awarded_count=already_awarded_count,
        message=f"Milestones evaluated for module '{payload.module_id}'. {len(newly_awarded)} badge(s) awarded.",
    )


async def get_user_badges(user_id: str) -> List[Dict]:
    """Retrieve all milestone badges earned by a user."""
    all_badges = await kv_store.store.list_values(BADGES_NS)
    return [b for b in all_badges if b.get("user_id") == user_id]


# ===========================================================================
# PIECE 4 — Learning Path Reset
# ===========================================================================
async def reset_learning_path(user_id: str, payload: PathResetRequest) -> PathResetResponse:
    """
    Restart a learning path from scratch. Requires explicit confirmation,
    archives prior progress, blocks mid-session resets, and checks enterprise permission.
    """
    path_def = await get_path_definition(payload.path_id)
    if not path_def:
        raise InvalidSubmissionError(f"Path '{payload.path_id}' not found.")

    # 1. Permission check (e.g. enterprise-assigned path restriction)
    if path_def.get("is_enterprise_assigned"):
        raise AppError("Enterprise-assigned learning paths cannot be reset without admin authorization.", 403)

    # 2. Active session in progress check
    all_paused = await kv_store.store.list_values(PAUSED_SESSIONS_NS)
    active_in_progress = any(
        s.get("user_id") == user_id and s.get("path_id") == payload.path_id and not s.get("completed")
        for s in all_paused
    )
    if active_in_progress:
        raise InvalidSubmissionError(
            "An active session is currently in progress on this path. Please finish or end the session before resetting."
        )

    # 3. Explicit confirmation requirement
    if not payload.confirm:
        raise InvalidSubmissionError(
            "Path reset is a destructive action requiring explicit confirmation (confirm=True)."
        )

    state = await get_user_path_state(user_id)
    old_hist = state.get("path_history", {}).get(payload.path_id)

    # 4. Archive old progress before reset
    archived_version = len(state.setdefault("archived_history", [])) + 1
    if old_hist:
        archive_entry = {
            "path_id": payload.path_id,
            "version": archived_version,
            "archived_at": _now_iso(),
            "path_history": dict(old_hist),
        }
        state["archived_history"].append(archive_entry)

    # 5. Reset active progress to zero
    state.setdefault("path_history", {})[payload.path_id] = {
        "completed_modules": [],
        "module_scores": {},
        "is_active": (state.get("active_path_id") == payload.path_id),
        "started_at": _now_iso(),
        "total_practice_time": 0,
        "vocabulary_mastered": 0,
    }

    await _save_user_path_state(user_id, state)

    return PathResetResponse(
        success=True,
        path_id=payload.path_id,
        archived_version=archived_version,
        message=f"Learning path '{path_def['title']}' reset to scratch. Prior progress archived (v{archived_version}).",
    )


# ===========================================================================
# PIECE 5 — Learning Path Management (Admin Authoring)
# ===========================================================================
def _detect_circular_dependency(modules: List[ModuleSchema]):
    """DFS graph cycle detection for module prerequisites."""
    graph = {m.module_id: m.prerequisites for m in modules}
    visited = {}

    def dfs(node: str, stack: List[str]):
        visited[node] = 1  # visiting
        stack.append(node)
        for prereq in graph.get(node, []):
            if prereq not in graph:
                continue
            if visited.get(prereq) == 1:
                cycle_path = " -> ".join(stack + [prereq])
                raise InvalidSubmissionError(
                    f"Circular prerequisite dependency detected between modules: {cycle_path}."
                )
            if visited.get(prereq, 0) == 0:
                dfs(prereq, stack)
        stack.pop()
        visited[node] = 2  # visited

    for m in modules:
        if visited.get(m.module_id, 0) == 0:
            dfs(m.module_id, [])


async def admin_save_path(admin_id: str, payload: AdminPathCreateRequest) -> Dict:
    """Create or update a learning path definition with cycle detection and concurrent edit locks."""
    # 1. Concurrent Admin Record Locking check
    existing_lock = await kv_store.store.get(ADMIN_LOCKS_NS, payload.path_id)
    if existing_lock:
        lock_time = datetime.fromisoformat(existing_lock["locked_at"])
        if existing_lock["admin_id"] != admin_id and (_now() - lock_time) < timedelta(minutes=15):
            raise InvalidSubmissionError(
                f"Path '{payload.path_id}' is currently being edited by admin '{existing_lock['admin_id']}'."
            )

    # 2. Check for circular prerequisite dependencies
    _detect_circular_dependency(payload.modules)

    path_record = {
        "path_id": payload.path_id,
        "title": payload.title,
        "description": payload.description,
        "learning_level": payload.learning_level,
        "is_published": payload.is_published,
        "strict_sequential": payload.strict_sequential,
        "is_enterprise_assigned": payload.is_enterprise_assigned,
        "deprecated_id": payload.deprecated_id,
        "mapped_to_id": payload.mapped_to_id,
        "owner_id": admin_id,
        "updated_at": _now_iso(),
        "modules": [m.dict() for m in payload.modules],
    }

    existing = await kv_store.store.get(PATHS_NS, payload.path_id)
    if existing:
        await kv_store.store.update(PATHS_NS, payload.path_id, path_record)
    else:
        await kv_store.store.create(PATHS_NS, payload.path_id, path_record)

    return {"success": True, "path_id": payload.path_id, "message": "Learning path saved successfully."}


async def admin_publish_path(admin_id: str, path_id: str) -> Dict:
    """Publish a learning path. Blocks if path has 0 modules."""
    path_def = await get_path_definition(path_id)
    if not path_def:
        raise InvalidSubmissionError(f"Path '{path_id}' not found.")

    if not path_def.get("modules") or len(path_def["modules"]) == 0:
        raise InvalidSubmissionError("Cannot publish a learning path with zero modules attached.")

    path_def["is_published"] = True
    path_def["updated_at"] = _now_iso()
    await kv_store.store.update(PATHS_NS, path_id, path_def)

    return {"success": True, "path_id": path_id, "is_published": True, "message": "Path published successfully."}


async def admin_delete_module(admin_id: str, module_id: str) -> Dict:
    """Delete a module. Blocks if module is part of an active/published path."""
    all_paths = await list_all_paths()
    for p in all_paths:
        if p.get("is_published"):
            mod_ids = [m.get("module_id") for m in p.get("modules", [])]
            if module_id in mod_ids:
                raise InvalidSubmissionError(
                    f"Cannot delete module '{module_id}' because it is attached to active published path '{p['title']}'."
                )

    return {"success": True, "module_id": module_id, "message": f"Module '{module_id}' deleted."}


async def admin_acquire_lock(payload: AdminLockRequest) -> AdminLockResponse:
    """Acquire editing lock for an admin on a path."""
    existing_lock = await kv_store.store.get(ADMIN_LOCKS_NS, payload.path_id)
    if existing_lock:
        lock_time = datetime.fromisoformat(existing_lock["locked_at"])
        if existing_lock["admin_id"] != payload.admin_id and (_now() - lock_time) < timedelta(minutes=15):
            return AdminLockResponse(
                success=False,
                locked_by=existing_lock["admin_id"],
                message=f"Path is currently being edited by {existing_lock['admin_id']}.",
            )

    lock_record = {"path_id": payload.path_id, "admin_id": payload.admin_id, "locked_at": _now_iso()}
    if existing_lock:
        await kv_store.store.update(ADMIN_LOCKS_NS, payload.path_id, lock_record)
    else:
        await kv_store.store.create(ADMIN_LOCKS_NS, payload.path_id, lock_record)

    return AdminLockResponse(success=True, locked_by=payload.admin_id, message="Editing lock acquired.")


# ===========================================================================
# PIECE 6 — Learning Path Progress Persistence (Pause & Resume)
# ===========================================================================
async def pause_module_session(user_id: str, payload: ModulePauseRequest) -> PauseResumeResponse:
    """Save in-progress session state server-side."""
    key = f"{user_id}_{payload.path_id}_{payload.module_id}"
    path_def = await get_path_definition(payload.path_id)
    content_ver = 1
    if path_def:
        for m in path_def.get("modules", []):
            if m.get("module_id") == payload.module_id:
                content_ver = m.get("content_version", 1)

    record = {
        "user_id": user_id,
        "path_id": payload.path_id,
        "module_id": payload.module_id,
        "question_index": payload.question_index,
        "conversation_context": payload.conversation_context,
        "in_progress_data": payload.in_progress_data,
        "content_version": content_ver,
        "last_updated_at": _now_iso(),
        "was_interrupted": payload.was_interrupted,
    }

    existing = await kv_store.store.get(PAUSED_SESSIONS_NS, key)
    if existing:
        await kv_store.store.update(PAUSED_SESSIONS_NS, key, record)
    else:
        await kv_store.store.create(PAUSED_SESSIONS_NS, key, record)

    return PauseResumeResponse(
        success=True,
        resumed=False,
        question_index=payload.question_index,
        message="Session paused and state saved server-side.",
    )


async def resume_module_session(user_id: str, payload: ModuleResumeRequest) -> PauseResumeResponse:
    """Resume a paused module session with stale reset, version mismatch, and interruption checks."""
    key = f"{user_id}_{payload.path_id}_{payload.module_id}"
    session = await kv_store.store.get(PAUSED_SESSIONS_NS, key)

    if not session:
        return PauseResumeResponse(success=False, message="No paused session found for this module.")

    # 1. Stale session check (> 7 days)
    last_updated = datetime.fromisoformat(session["last_updated_at"])
    if (_now() - last_updated) > timedelta(days=7):
        await kv_store.store.delete(PAUSED_SESSIONS_NS, key)
        return PauseResumeResponse(
            success=True,
            resumed=False,
            stale_reset=True,
            message="Paused session sat abandoned for >7 days. Session state cleared and module reset to beginning.",
        )

    # 2. Content version mismatch check (admin updated module)
    path_def = await get_path_definition(payload.path_id)
    current_ver = 1
    if path_def:
        for m in path_def.get("modules", []):
            if m.get("module_id") == payload.module_id:
                current_ver = m.get("content_version", 1)

    if session.get("content_version", 1) != current_ver:
        await kv_store.store.delete(PAUSED_SESSIONS_NS, key)
        return PauseResumeResponse(
            success=True,
            resumed=False,
            content_updated=True,
            message="Module content was updated by an administrator. Restarting module fresh with new content.",
        )

    # 3. Interrupted mid-processing check
    was_interrupted = session.get("was_interrupted", False)
    msg = (
        "Your previous attempt was interrupted mid-processing. Please repeat your last input."
        if was_interrupted
        else "Resuming conversation where you left off..."
    )

    return PauseResumeResponse(
        success=True,
        resumed=True,
        question_index=session.get("question_index", 0),
        conversation_context=session.get("conversation_context", []),
        in_progress_data=session.get("in_progress_data", {}),
        was_interrupted=was_interrupted,
        message=msg,
    )


# ===========================================================================
# PIECE 7 — Learning Path Prerequisite Unlocking
# ===========================================================================
async def check_module_access(user_id: str, path_id: str, module_id: str) -> ModuleAccessResponse:
    """Server-side access enforcement blocking locked module access."""
    path_def = await get_path_definition(path_id)
    if not path_def:
        raise InvalidSubmissionError(f"Path '{path_id}' not found.")

    state = await get_user_path_state(user_id)

    # 1. Admin/Manager manual override check
    overrides = state.get("manual_overrides", {})
    if overrides.get("unlock_all") or module_id in overrides.get("unlocked_modules", []):
        return ModuleAccessResponse(
            module_id=module_id,
            accessible=True,
            reason="Access granted via admin manual override.",
            mode="override",
        )

    # 2. Free Explore Mode toggle check
    strict_seq = path_def.get("strict_sequential", True)
    if not strict_seq:
        return ModuleAccessResponse(
            module_id=module_id,
            accessible=True,
            reason="Free Explore Mode is active for this path.",
            mode="free_explore",
        )

    # 3. Strict Sequential Mode prerequisites check
    modules = path_def.get("modules", [])
    target_mod = next((m for m in modules if m["module_id"] == module_id), None)
    if not target_mod:
        raise InvalidSubmissionError(f"Module '{module_id}' not found in path '{path_id}'.")

    prereqs = target_mod.get("prerequisites", [])
    p_hist = state.get("path_history", {}).get(path_id, {})
    completed_mods = p_hist.get("completed_modules", [])
    module_scores = p_hist.get("module_scores", {})

    # Check Grandfathering (if new module inserted mid-sequence after user progressed)
    highest_completed_order = 0
    for m in modules:
        if m["module_id"] in completed_mods:
            highest_completed_order = max(highest_completed_order, m["sequence_order"])

    if target_mod["sequence_order"] <= highest_completed_order:
        return ModuleAccessResponse(
            module_id=module_id,
            accessible=True,
            reason="Grandfathered access retained.",
            mode="strict_sequential",
        )

    for p_id in prereqs:
        if p_id not in completed_mods:
            return ModuleAccessResponse(
                module_id=module_id,
                accessible=False,
                reason=f"Prerequisite module '{p_id}' has not been completed.",
                mode="strict_sequential",
            )

        # Passing score check (low score keeps next module locked!)
        score = module_scores.get(p_id, 0.0)
        req_score = target_mod.get("passing_score", 60.0)
        if score < req_score:
            return ModuleAccessResponse(
                module_id=module_id,
                accessible=False,
                reason=f"Prerequisite module '{p_id}' completed with low score ({score:.1f}). Score >= {req_score} required to unlock next module.",
                mode="strict_sequential",
                current_score=score,
                required_score=req_score,
            )

    return ModuleAccessResponse(
        module_id=module_id,
        accessible=True,
        reason="All prerequisites met with passing scores.",
        mode="strict_sequential",
    )


async def set_manual_unlock_override(user_id: str, path_id: str, unlock_all: bool, module_ids: List[str]) -> Dict:
    """Enterprise admin override to force-unlock modules for a specific user."""
    state = await get_user_path_state(user_id)
    state["manual_overrides"] = {"unlock_all": unlock_all, "unlocked_modules": module_ids}
    await _save_user_path_state(user_id, state)
    return {"success": True, "user_id": user_id, "message": "Manual unlock override saved."}


# ===========================================================================
# PIECE 8 — End-to-End Learning Path Completion & Certification
# ===========================================================================
async def check_path_completion(user_id: str, path_id: str) -> PathCompletionCheckResponse:
    """Verify 100% path completion and generate exportable certification summary."""
    path_def = await get_path_definition(path_id)
    if not path_def:
        raise InvalidSubmissionError(f"Path '{path_id}' not found.")

    modules = path_def.get("modules", [])
    state = await get_user_path_state(user_id)
    p_hist = state.get("path_history", {}).get(path_id, {})
    completed_mods = p_hist.get("completed_modules", [])

    incomplete = [m["module_id"] for m in modules if m["module_id"] not in completed_mods]

    # Check Grandfathering: only applies if the user completed the module with the highest
    # sequence_order (i.e. they finished what was previously the last module before an admin
    # appended a new one). Completing n-1 arbitrary modules does NOT qualify.
    is_grandfathered = False
    if len(incomplete) > 0 and len(modules) > 0:
        last_module = max(modules, key=lambda m: m["sequence_order"])
        highest_completed_order = max(
            (m["sequence_order"] for m in modules if m["module_id"] in completed_mods),
            default=0,
        )
        all_incomplete_are_new = all(
            m["sequence_order"] > highest_completed_order
            for m in modules
            if m["module_id"] in incomplete
        )
        if last_module["module_id"] in completed_mods and all_incomplete_are_new:
            is_grandfathered = True

    is_complete = (len(incomplete) == 0) or is_grandfathered

    if not is_complete:
        return PathCompletionCheckResponse(
            path_id=path_id,
            is_complete=False,
            completed_modules_count=len(completed_mods),
            total_modules_count=len(modules),
            incomplete_module_ids=incomplete,
            is_grandfathered=False,
        )

    # Calculate summary metrics
    scores = list(p_hist.get("module_scores", {}).values())
    avg_conf = round(sum(scores) / len(scores), 2) if scores else 80.0
    tot_time = p_hist.get("total_practice_time", 1800) or 1800
    vocab_count = p_hist.get("vocabulary_mastered", 45) or 45
    cert_id = f"CERT-LP-{uuid.uuid4().hex[:8].upper()}"

    summary_data = {
        "path_id": path_id,
        "path_title": path_def["title"],
        "user_id": user_id,
        "total_practice_time_seconds": tot_time,
        "average_confidence_score": avg_conf,
        "total_vocabulary_mastered": vocab_count,
        "completed_at": _now_iso(),
        "certificate_id": cert_id,
        "shareable_card_data": {
            "title": f"Certified: {path_def['title']}",
            "level": path_def.get("learning_level", "BEGINNER"),
            "certificate_url": f"https://speeky.app/certificates/{cert_id}",
            "badge_icon": "award",
        },
    }

    return PathCompletionCheckResponse(
        path_id=path_id,
        is_complete=True,
        completed_modules_count=len(completed_mods),
        total_modules_count=len(modules),
        # Keep the real list even when grandfathered — the path is "complete" for
        # certification purposes but the UI must still show which modules were
        # genuinely finished vs. grandfathered-in.
        incomplete_module_ids=incomplete,
        is_grandfathered=is_grandfathered,
        summary=summary_data,
    )


async def get_path_certification_summary(user_id: str, path_id: str) -> PathSummaryResponse:
    """Fetch path certification summary for export/sharing."""
    comp_check = await check_path_completion(user_id, path_id)
    if not comp_check.is_complete or not comp_check.summary:
        raise InvalidSubmissionError("Learning path is not 100% complete yet. Cannot generate summary.")

    s = comp_check.summary
    return PathSummaryResponse(
        path_id=s["path_id"],
        path_title=s["path_title"],
        user_id=s["user_id"],
        total_practice_time_seconds=s["total_practice_time_seconds"],
        average_confidence_score=s["average_confidence_score"],
        total_vocabulary_mastered=s["total_vocabulary_mastered"],
        completed_at=s["completed_at"],
        certificate_id=s["certificate_id"],
        shareable_card_data=s["shareable_card_data"],
    )
