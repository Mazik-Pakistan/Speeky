from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Piece 1: Streak Freeze & Vacation Mode ────────────────────────────────────
class StreakInfoResponse(BaseModel):
    current_streak: int
    highest_streak: int
    freeze_tokens: int
    last_practice_date: Optional[str] = None
    active_freezes: List[str] = []
    last_makeup_drill_month: Optional[str] = None


class ActivateFreezeRequest(BaseModel):
    date: str  # YYYY-MM-DD


class ActivateFreezeResponse(BaseModel):
    success: bool
    message: str
    freeze_tokens_remaining: int
    active_freezes: List[str]


class PracticeSessionLogRequest(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD (default: today)
    duration_seconds: int = 300
    fluency_score: float = 75.0
    vocabulary_score: float = 75.0
    pronunciation_score: Optional[float] = None
    transcript: Optional[str] = None


class PracticeSessionLogResponse(BaseModel):
    session_id: str
    date: str
    current_streak: int
    highest_streak: int
    freeze_tokens: int
    token_refunded: bool = False
    tokens_earned: int = 0
    message: str


class MakeupDrillRequest(BaseModel):
    note: Optional[str] = None


class MakeupDrillResponse(BaseModel):
    success: bool
    restored_streak: int
    message: str


# ── Piece 2: Confidence Methodology & Dispute ─────────────────────────────────
class ComponentScoreDetail(BaseModel):
    weight: float
    recent_average: Optional[float] = None
    description: str


class ConfidenceBreakdownResponse(BaseModel):
    current_score: float
    explanation: str
    components: Dict[str, ComponentScoreDetail]
    session_count: int
    insufficient_data: bool = False


class DisputeScoreRequest(BaseModel):
    session_id: str
    reason: str


class DisputeScoreResponse(BaseModel):
    dispute_id: str
    session_id: str
    status: str
    message: str


# ── Piece 3: Badge Catalog & Locked Preview ──────────────────────────────────
class BadgeStatusSchema(BaseModel):
    badge_id: str
    title: str
    category: str  # "streak", "practice_time", "vocabulary", "special"
    description: str
    icon: str
    earned: bool
    earned_at: Optional[str] = None
    requirement_text: str
    current_progress: int
    target_requirement: int
    progress_label: str


class BadgeCatalogResponse(BaseModel):
    total_badges: int
    earned_count: int
    badges: List[BadgeStatusSchema]


# ── Piece 4: Progress Report Export ──────────────────────────────────────────
class ProgressReportRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD


class MonthlyRollupSummary(BaseModel):
    month: str  # YYYY-MM
    sessions_count: int
    avg_confidence_score: float
    avg_vocabulary_score: float
    total_practice_seconds: int


class ProgressReportResponse(BaseModel):
    start_date: str
    end_date: str
    session_count: int
    confidence_score_trend: List[Dict]
    vocabulary_growth: List[Dict]
    total_practice_time_seconds: int
    badges_earned: List[str]
    is_rollup: bool = False
    monthly_rollups: List[MonthlyRollupSummary] = []
    note: Optional[str] = None


# ── Piece 5: Streak Restore Appeal ───────────────────────────────────────────
class StreakAppealRequest(BaseModel):
    date_of_break: str  # YYYY-MM-DD
    reason: str
    has_evidence: bool = False
    evidence_note: Optional[str] = None


class StreakAppealResponse(BaseModel):
    appeal_id: str
    status: str  # "approved", "declined", "flagged_for_manual_review"
    message: str
    restored_streak: Optional[int] = None


# ── Piece 6: Historical Data Retention & Long-Range Performance ────────────────
class SessionDataPoint(BaseModel):
    session_id: str
    timestamp: str
    confidence_score: float
    fluency_score: float
    vocabulary_score: float
    pronunciation_score: Optional[float] = None
    duration_seconds: int
    is_outlier: bool = False


class AggregatedDataPoint(BaseModel):
    period_label: str  # e.g., "2026-W29" or "2026-07"
    start_date: str
    end_date: str
    session_count: int
    avg_confidence: float
    avg_vocabulary: float
    total_practice_seconds: int
    best_outlier_session: Optional[SessionDataPoint] = None
    is_gap: bool = False


class HistoricalDataResponse(BaseModel):
    time_range: str  # "week", "month", "year", "all_time"
    aggregation_level: str  # "raw", "weekly", "monthly"
    raw_sessions: Optional[List[SessionDataPoint]] = None
    aggregated_points: Optional[List[AggregatedDataPoint]] = None


class ExpandDataPointResponse(BaseModel):
    period_label: str
    sessions: List[SessionDataPoint]
