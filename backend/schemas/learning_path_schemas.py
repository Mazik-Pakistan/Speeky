from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Piece 1: Recommendation ───────────────────────────────────────────────────
class RecommendationResponse(BaseModel):
    recommended_path_id: str
    path_title: str
    reasoning: str
    confidence_score: float
    learning_level: str
    is_fallback: bool = False
    available_paths: List[Dict] = []


class AcceptRecommendationRequest(BaseModel):
    path_id: str


# ── Piece 2: Path Switching ──────────────────────────────────────────────────
class PathSwitchRequest(BaseModel):
    target_path_id: str
    confirm: bool = False
    unsaved_progress: Optional[Dict] = None
    request_id: Optional[str] = None


class PathSwitchResponse(BaseModel):
    success: bool
    active_path_id: str
    previous_path_id: Optional[str] = None
    confirmation_required: bool = False
    warning: Optional[str] = None
    message: str


# ── Piece 3: Milestone & Achievement Tracking ─────────────────────────────────
class MilestoneEvaluateRequest(BaseModel):
    path_id: str
    module_id: str
    score: float = 80.0
    completed_at: Optional[str] = None
    is_offline: bool = False
    corrupted_progress: bool = False


class MilestoneEvaluateResponse(BaseModel):
    module_id: str
    awarded_badges: List[str] = []
    already_awarded_count: int = 0
    message: str


# ── Piece 4: Learning Path Reset ─────────────────────────────────────────────
class PathResetRequest(BaseModel):
    path_id: str
    confirm: bool = False


class PathResetResponse(BaseModel):
    success: bool
    path_id: str
    archived_version: int
    message: str


# ── Piece 5: Admin Authoring ─────────────────────────────────────────────────
class ModuleSchema(BaseModel):
    module_id: str
    title: str
    sequence_order: int
    prerequisites: List[str] = []
    passing_score: float = 60.0
    content: Optional[str] = ""
    content_version: int = 1


class AdminPathCreateRequest(BaseModel):
    path_id: str
    title: str
    description: Optional[str] = ""
    learning_level: str = "BEGINNER"
    is_published: bool = False
    strict_sequential: bool = True
    modules: List[ModuleSchema] = []
    is_enterprise_assigned: bool = False
    deprecated_id: Optional[str] = None
    mapped_to_id: Optional[str] = None


class AdminLockRequest(BaseModel):
    path_id: str
    admin_id: str


class AdminLockResponse(BaseModel):
    success: bool
    locked_by: Optional[str] = None
    message: str


# ── Piece 6: Pause & Resume ─────────────────────────────────────────────────
class ModulePauseRequest(BaseModel):
    path_id: str
    module_id: str
    question_index: int = 0
    conversation_context: List[Dict] = []
    in_progress_data: Dict = {}
    was_interrupted: bool = False


class ModuleResumeRequest(BaseModel):
    path_id: str
    module_id: str


class PauseResumeResponse(BaseModel):
    success: bool
    resumed: bool = False
    question_index: int = 0
    conversation_context: List[Dict] = []
    in_progress_data: Dict = {}
    stale_reset: bool = False
    content_updated: bool = False
    was_interrupted: bool = False
    message: str = ""


# ── Piece 7: Prerequisite Unlocking ─────────────────────────────────────────
class ModuleAccessResponse(BaseModel):
    module_id: str
    accessible: bool
    reason: str
    mode: str
    current_score: Optional[float] = None
    required_score: float = 60.0


class ManualUnlockOverrideRequest(BaseModel):
    target_user_id: str
    path_id: str
    unlock_all: bool = True
    module_ids: List[str] = []


# ── Piece 8: Completion & Certification ─────────────────────────────────────
class PathCompletionCheckResponse(BaseModel):
    path_id: str
    is_complete: bool
    completed_modules_count: int
    total_modules_count: int
    incomplete_module_ids: List[str] = []
    is_grandfathered: bool = False
    summary: Optional[Dict] = None


class PathSummaryResponse(BaseModel):
    path_id: str
    path_title: str
    user_id: str
    total_practice_time_seconds: int
    average_confidence_score: float
    total_vocabulary_mastered: int
    completed_at: str
    certificate_id: str
    shareable_card_data: Dict
