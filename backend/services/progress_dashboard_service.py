"""
Progress Dashboard Tracking Service (PDG-US-10 & PDG-US-14)

Aggregates data across all completed learning sessions (BaselineAssessment, CoachingSession,
ScenarioSession, PublicSpeakingSession, AccentAssessment, PronunciationAttempt) into a visual,
time-series progress dashboard.

Features & Exception Handling:
  - Immediate post-session update (computed on read, no stale caching during normal operation).
  - Confidence Score returned as the central, top-line primary metric.
  - Time-series data points shaped for visual graph trend lines.
  - E-01 (Data Sync Failure): Graceful fallback to last known good snapshot with sync_status="stale".
  - E-02 (Empty State - Day 1): Zero-state payload with motivational prompt for day-1 users.
  - E-03 (Corrupted Session Data): Drops outlier scores (> 100 or < 0) from visual aggregates and flags the row.
  - E-04 (Streak Calculation): Rolling 24-48 hour UTC window calculation to prevent timezone breaks.

Also covers the gamification layer added alongside the above: streak freeze/vacation mode,
confidence methodology transparency & dispute, badge catalog, progress report export, streak
restore appeal, and historical data retention/chart performance (Pieces 1-6 below).
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import Depends
from fastapi.responses import JSONResponse
from prisma import Json

from lib import confidence_engine, kv_store, pii
from lib.prisma_client import db
from middlewares.auth_middleware import require_auth
from schemas.progress_dashboard_schemas import (
    ActivateFreezeRequest,
    ActivateFreezeResponse,
    AggregatedDataPoint,
    BadgeCatalogResponse,
    BadgeStatusSchema,
    ComponentScoreDetail,
    ConfidenceBreakdownResponse,
    DisputeScoreRequest,
    DisputeScoreResponse,
    ExpandDataPointResponse,
    HistoricalDataResponse,
    MakeupDrillRequest,
    MakeupDrillResponse,
    MonthlyRollupSummary,
    PracticeSessionLogRequest,
    PracticeSessionLogResponse,
    PrimaryMetricSchema,
    ProgressDashboardMetricsSchema,
    ProgressDashboardResponseSchema,
    ProgressReportRequest,
    ProgressReportResponse,
    SessionDataPoint,
    StreakAppealRequest,
    StreakAppealResponse,
    StreakInfoResponse,
    TrendPointSchema,
)
from utils.feature_errors import (
    InvalidSubmissionError,
    RateLimitedError,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

# Namespaces for KvStore persistence
STREAK_NS = "progress_streak"
SESSIONS_NS = "progress_sessions"
DISPUTES_NS = "progress_disputes"
BADGES_NS = "progress_badges"
APPEALS_NS = "progress_appeals"
DASHBOARD_SNAPSHOT_NS = "dashboard_snapshots"
MAX_DAILY_VOCAB_GROWTH = 15

DAY1_MOTIVATIONAL_PROMPT = "Complete your first session to see your progress growth!"
SYNC_STALE_MESSAGE = "Syncing recent data... Unable to reach server, showing last-known-good metrics."

# PDG-US-14 copy used by the legacy /overview payload (Vocabulary Growth panel).
_EMPTY_STATE_MESSAGE = "Complete a Scenario to start collecting words!"
_ZERO_GROWTH_MESSAGE = "Great consistency! Try a new Scenario to discover advanced words."

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _month_str(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m")


def _parse_date(d_str: str) -> datetime:
    return datetime.strptime(d_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


# ── Helper: Get or Init Streak State ──────────────────────────────────────────
async def get_user_streak_state(user_id: str) -> Dict:
    state = await kv_store.store.get(STREAK_NS, user_id)
    if not state:
        state = {
            "user_id": user_id,
            "current_streak": 0,
            "highest_streak": 0,
            "freeze_tokens": 0,
            "last_practice_date": None,
            "active_freezes": [],
            "last_makeup_drill_month": None,
            "milestones_awarded": [],
        }
        await kv_store.store.create(STREAK_NS, user_id, state)
    return state


async def _save_user_streak_state(user_id: str, state: Dict):
    await kv_store.store.update(STREAK_NS, user_id, state)


# ── Helper: Get User Sessions ────────────────────────────────────────────────
async def get_user_sessions(user_id: str) -> List[Dict]:
    all_sessions = await kv_store.store.list_values(SESSIONS_NS)
    user_s = [s for s in all_sessions if s.get("user_id") == user_id]
    # Sort by timestamp ascending
    user_s.sort(key=lambda x: x.get("timestamp", ""))
    return user_s


# ── Piece 1: Streak Freeze & Vacation Mode ────────────────────────────────────
async def get_streak_info(user_id: str) -> StreakInfoResponse:
    state = await get_user_streak_state(user_id)
    return StreakInfoResponse(
        current_streak=state["current_streak"],
        highest_streak=state["highest_streak"],
        freeze_tokens=state["freeze_tokens"],
        last_practice_date=state.get("last_practice_date"),
        active_freezes=state.get("active_freezes", []),
        last_makeup_drill_month=state.get("last_makeup_drill_month"),
    )


async def activate_freeze(payload: ActivateFreezeRequest, user_id: str) -> ActivateFreezeResponse:
    state = await get_user_streak_state(user_id)
    target_date = payload.date.strip()

    if target_date in state.get("active_freezes", []):
        return ActivateFreezeResponse(
            success=True,
            message=f"Freeze is already active for {target_date}.",
            freeze_tokens_remaining=state["freeze_tokens"],
            active_freezes=state["active_freezes"],
        )

    if state["freeze_tokens"] <= 0:
        raise InvalidSubmissionError("No freeze tokens available to activate a freeze.")

    state["freeze_tokens"] -= 1
    state.setdefault("active_freezes", []).append(target_date)
    await _save_user_streak_state(user_id, state)

    return ActivateFreezeResponse(
        success=True,
        message=f"Freeze activated for {target_date}. 1 freeze token consumed.",
        freeze_tokens_remaining=state["freeze_tokens"],
        active_freezes=state["active_freezes"],
    )


async def log_practice_session(
    payload: PracticeSessionLogRequest, user_id: str
) -> PracticeSessionLogResponse:
    state = await get_user_streak_state(user_id)
    session_date_str = payload.date or _today_str()
    session_dt = _parse_date(session_date_str)

    # 1. Store session entry
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session_record = {
        "session_id": session_id,
        "user_id": user_id,
        "date": session_date_str,
        "timestamp": session_dt.isoformat(),
        "duration_seconds": payload.duration_seconds,
        "fluency_score": payload.fluency_score,
        "vocabulary_score": payload.vocabulary_score,
        "pronunciation_score": payload.pronunciation_score,
        "transcript": payload.transcript,
    }
    await kv_store.store.create(SESSIONS_NS, session_id, session_record)

    # 2. Check if active freeze on this date -> Refund token
    token_refunded = False
    active_freezes = state.get("active_freezes", [])
    if session_date_str in active_freezes:
        active_freezes.remove(session_date_str)
        state["freeze_tokens"] += 1
        token_refunded = True

    # 3. Calculate streak progression
    last_p_str = state.get("last_practice_date")
    streak_broken = False

    if not last_p_str:
        # First session ever
        state["current_streak"] = 1
    else:
        last_dt = _parse_date(last_p_str)
        day_diff = (session_dt.date() - last_dt.date()).days

        if day_diff == 0:
            # Practiced again on the same day
            pass
        elif day_diff == 1:
            # Consecutive day
            state["current_streak"] += 1
        elif day_diff > 1:
            # Missed days between last_dt + 1 day and session_dt - 1 day
            missed_count = day_diff - 1
            protected_days = 0

            for i in range(1, day_diff):
                m_date = (last_dt + timedelta(days=i)).strftime("%Y-%m-%d")
                if m_date in active_freezes:
                    protected_days += 1
                elif state["freeze_tokens"] > 0:
                    # Automatically protect using available token
                    state["freeze_tokens"] -= 1
                    state.setdefault("active_freezes", []).append(m_date)
                    protected_days += 1
                else:
                    # Unprotected day -> streak breaks!
                    streak_broken = True

            if streak_broken:
                state["current_streak"] = 1
            else:
                state["current_streak"] += 1

    # 4. Award milestone freeze tokens (1 token per 7 days of streak)
    curr_s = state["current_streak"]
    tokens_earned = 0
    milestones_awarded = state.setdefault("milestones_awarded", [])
    if curr_s >= 7:
        num_milestones = curr_s // 7
        for m in range(1, num_milestones + 1):
            m_day = m * 7
            if m_day not in milestones_awarded:
                milestones_awarded.append(m_day)
                state["freeze_tokens"] += 1
                tokens_earned += 1

    state["highest_streak"] = max(state["highest_streak"], curr_s)
    state["last_practice_date"] = session_date_str
    await _save_user_streak_state(user_id, state)

    # 5. Evaluate badges after logging session
    await _evaluate_user_badges(user_id, state)

    msg = f"Practice session logged for {session_date_str}."
    if token_refunded:
        msg += " Freeze token refunded because you practiced on a frozen day."
    if tokens_earned > 0:
        msg += f" Earned {tokens_earned} freeze token(s) for streak milestone!"

    return PracticeSessionLogResponse(
        session_id=session_id,
        date=session_date_str,
        current_streak=state["current_streak"],
        highest_streak=state["highest_streak"],
        freeze_tokens=state["freeze_tokens"],
        token_refunded=token_refunded,
        tokens_earned=tokens_earned,
        message=msg,
    )


async def perform_makeup_drill(payload: MakeupDrillRequest, user_id: str) -> MakeupDrillResponse:
    state = await get_user_streak_state(user_id)
    curr_month = _month_str()

    if state.get("last_makeup_drill_month") == curr_month:
        raise InvalidSubmissionError(
            "One-time makeup drill has already been used this calendar month."
        )

    if state["freeze_tokens"] > 0:
        raise InvalidSubmissionError(
            "Makeup drill is only available when you have zero freeze tokens."
        )

    # Restore streak by 1
    state["current_streak"] += 1
    state["highest_streak"] = max(state["highest_streak"], state["current_streak"])
    state["last_makeup_drill_month"] = curr_month
    await _save_user_streak_state(user_id, state)

    return MakeupDrillResponse(
        success=True,
        restored_streak=state["current_streak"],
        message=f"Makeup drill completed successfully! Streak restored to {state['current_streak']}.",
    )


# ── Piece 2: Confidence Methodology Transparency & Dispute ───────────────────
async def get_confidence_breakdown(user_id: str) -> ConfidenceBreakdownResponse:
    sessions = await get_user_sessions(user_id)

    if len(sessions) < 2:
        return ConfidenceBreakdownResponse(
            current_score=sessions[0]["fluency_score"] if len(sessions) == 1 else 0.0,
            explanation="Insufficient data for a full breakdown. At least 2 completed sessions are required to calculate confidence trends.",
            components={
                "fluency": ComponentScoreDetail(weight=50.0, recent_average=None, description="Flow and naturalness of speech"),
                "vocabulary": ComponentScoreDetail(weight=30.0, recent_average=None, description="Word choice and variety"),
                "pronunciation": ComponentScoreDetail(weight=20.0, recent_average=None, description="Clarity and accuracy of pronunciation"),
            },
            session_count=len(sessions),
            insufficient_data=True,
        )

    engine = confidence_engine.ConfidenceScoreEngine()
    for s in sessions:
        dt = _parse_date(s.get("date", _today_str()))
        score_obj = confidence_engine.SessionScore(
            timestamp=dt,
            fluency_score=s["fluency_score"],
            vocabulary_score=s["vocabulary_score"],
            pronunciation_score=s.get("pronunciation_score"),
            is_text_only=s.get("pronunciation_score") is None,
        )
        engine.add_session_score(score_obj)

    raw_bd = engine.get_confidence_breakdown()
    comp_map = {}
    for key, c_data in raw_bd.get("components", {}).items():
        comp_map[key] = ComponentScoreDetail(
            weight=c_data.get("weight", 0.0),
            recent_average=c_data.get("recent_average"),
            description=c_data.get("description", ""),
        )

    return ConfidenceBreakdownResponse(
        current_score=engine.get_confidence_score(),
        explanation=raw_bd.get("explanation", ""),
        components=comp_map,
        session_count=len(sessions),
        insufficient_data=False,
    )


async def get_session_detail(session_id: str, user_id: str) -> Dict:
    sess = await kv_store.store.get(SESSIONS_NS, session_id)
    if not sess or sess.get("user_id") != user_id:
        raise SessionNotFoundError(f"Session '{session_id}' not found.")
    return sess


async def dispute_session_score(
    payload: DisputeScoreRequest, user_id: str
) -> DisputeScoreResponse:
    # 1. Ensure session exists
    await get_session_detail(payload.session_id, user_id)

    # 2. Check dispute rate limit (max 3 per day per user)
    all_disputes = await kv_store.store.list_values(DISPUTES_NS)
    today_prefix = _today_str()
    user_today_disputes = [
        d for d in all_disputes
        if d.get("user_id") == user_id and d.get("created_at", "").startswith(today_prefix)
    ]

    if len(user_today_disputes) >= 3:
        raise RateLimitedError(
            "Dispute rate limit reached. You can submit up to 3 score disputes per day."
        )

    dispute_id = f"disp_{uuid.uuid4().hex[:12]}"
    dispute_record = {
        "dispute_id": dispute_id,
        "user_id": user_id,
        "session_id": payload.session_id,
        "reason": payload.reason,
        "status": "logged",
        "created_at": _now().isoformat(),
    }
    await kv_store.store.create(DISPUTES_NS, dispute_id, dispute_record)

    return DisputeScoreResponse(
        dispute_id=dispute_id,
        session_id=payload.session_id,
        status="logged",
        message="Dispute logged successfully. Our team will review the score without altering your current metrics.",
    )


# ── Piece 3: Full Badge Catalog & Locked Preview ─────────────────────────────
DEFINED_BADGES = [
    {
        "badge_id": "first_step",
        "title": "First Step",
        "category": "special",
        "description": "Completed your first practice session.",
        "icon": "footsteps",
        "requirement_text": "Complete 1 practice session",
        "target_requirement": 1,
    },
    {
        "badge_id": "streak_3",
        "title": "3-Day Warmup",
        "category": "streak",
        "description": "Maintained a 3-day practice streak.",
        "icon": "flame",
        "requirement_text": "Reach a 3-day streak",
        "target_requirement": 3,
    },
    {
        "badge_id": "streak_7",
        "title": "7-Day Warrior",
        "category": "streak",
        "description": "Maintained a 7-day practice streak.",
        "icon": "zap",
        "requirement_text": "Reach a 7-day streak",
        "target_requirement": 7,
    },
    {
        "badge_id": "streak_30",
        "title": "30-Day Master",
        "category": "streak",
        "description": "Maintained a 30-day practice streak.",
        "icon": "crown",
        "requirement_text": "Reach a 30-day streak",
        "target_requirement": 30,
    },
    {
        "badge_id": "time_15m",
        "title": "15-Minute Learner",
        "category": "practice_time",
        "description": "Accumulated 15 minutes of total practice time.",
        "icon": "clock",
        "requirement_text": "Practice for 900 seconds total",
        "target_requirement": 900,
    },
    {
        "badge_id": "time_1h",
        "title": "1-Hour Speaker",
        "category": "practice_time",
        "description": "Accumulated 1 hour of total practice time.",
        "icon": "award",
        "requirement_text": "Practice for 3600 seconds total",
        "target_requirement": 3600,
    },
    {
        "badge_id": "vocab_70",
        "title": "Vocab Explorer",
        "category": "vocabulary",
        "description": "Achieved a vocabulary score of 70 or higher.",
        "icon": "book-open",
        "requirement_text": "Score >= 70 in Vocabulary",
        "target_requirement": 70,
    },
    {
        "badge_id": "vocab_85",
        "title": "Lexical Scholar",
        "category": "vocabulary",
        "description": "Achieved a vocabulary score of 85 or higher.",
        "icon": "sparkles",
        "requirement_text": "Score >= 85 in Vocabulary",
        "target_requirement": 85,
    },
]


async def _evaluate_user_badges(user_id: str, streak_state: Dict):
    sessions = await get_user_sessions(user_id)
    all_badges = await kv_store.store.list_values(BADGES_NS)
    user_badges = {b["badge_id"]: b for b in all_badges if b.get("user_id") == user_id}

    total_time = sum(s.get("duration_seconds", 0) for s in sessions)
    max_streak = streak_state.get("highest_streak", 0)
    max_vocab = max([s.get("vocabulary_score", 0) for s in sessions], default=0)

    for bdef in DEFINED_BADGES:
        bid = bdef["badge_id"]
        if bid in user_badges:
            continue  # Already awarded — enforce badge uniqueness!

        earned = False
        if bid == "first_step" and len(sessions) >= 1:
            earned = True
        elif bid == "streak_3" and max_streak >= 3:
            earned = True
        elif bid == "streak_7" and max_streak >= 7:
            earned = True
        elif bid == "streak_30" and max_streak >= 30:
            earned = True
        elif bid == "time_15m" and total_time >= 900:
            earned = True
        elif bid == "time_1h" and total_time >= 3600:
            earned = True
        elif bid == "vocab_70" and max_vocab >= 70:
            earned = True
        elif bid == "vocab_85" and max_vocab >= 85:
            earned = True

        if earned:
            record = {
                "badge_id": bid,
                "user_id": user_id,
                "earned_at": _now().isoformat(),
            }
            await kv_store.store.create(BADGES_NS, f"{user_id}_{bid}", record)


async def get_badge_catalog(user_id: str) -> BadgeCatalogResponse:
    streak_state = await get_user_streak_state(user_id)
    await _evaluate_user_badges(user_id, streak_state)

    sessions = await get_user_sessions(user_id)
    all_badges = await kv_store.store.list_values(BADGES_NS)
    user_badges = {b["badge_id"]: b for b in all_badges if b.get("user_id") == user_id}

    total_time = sum(s.get("duration_seconds", 0) for s in sessions)
    curr_streak = streak_state.get("highest_streak", 0)
    max_vocab = max([int(s.get("vocabulary_score", 0)) for s in sessions], default=0)

    result_badges = []
    earned_count = 0

    for bdef in DEFINED_BADGES:
        bid = bdef["badge_id"]
        is_earned = bid in user_badges
        earned_at = user_badges[bid]["earned_at"] if is_earned else None

        # Compute current progress
        if bid == "first_step":
            prog = min(len(sessions), 1)
            target = 1
            unit = "session"
        elif bdef["category"] == "streak":
            prog = min(curr_streak, bdef["target_requirement"])
            target = bdef["target_requirement"]
            unit = "days"
        elif bdef["category"] == "practice_time":
            prog = min(total_time, bdef["target_requirement"])
            target = bdef["target_requirement"]
            unit = "seconds"
        elif bdef["category"] == "vocabulary":
            prog = min(max_vocab, bdef["target_requirement"])
            target = bdef["target_requirement"]
            unit = "pts"
        else:
            prog = 1 if is_earned else 0
            target = 1
            unit = "step"

        if is_earned:
            earned_count += 1

        result_badges.append(
            BadgeStatusSchema(
                badge_id=bid,
                title=bdef["title"],
                category=bdef["category"],
                description=bdef["description"],
                icon=bdef["icon"],
                earned=is_earned,
                earned_at=earned_at,
                requirement_text=bdef["requirement_text"],
                current_progress=prog,
                target_requirement=target,
                progress_label=f"{prog}/{target} {unit}",
            )
        )

    return BadgeCatalogResponse(
        total_badges=len(DEFINED_BADGES),
        earned_count=earned_count,
        badges=result_badges,
    )


# ── Piece 4: Progress Report Export ──────────────────────────────────────────
async def generate_progress_report(
    payload: ProgressReportRequest, user_id: str
) -> ProgressReportResponse:
    start_dt = _parse_date(payload.start_date)
    end_dt = _parse_date(payload.end_date)
    sessions = await get_user_sessions(user_id)

    # Filter sessions within date range
    range_sessions = []
    for s in sessions:
        s_dt = _parse_date(s.get("date", _today_str()))
        if start_dt.date() <= s_dt.date() <= end_dt.date():
            range_sessions.append(s)

    note = None
    if len(range_sessions) < 2:
        note = "Limited data available for this period."

    # Check for large date range (> 90 days) -> Monthly rollups
    is_rollup = (end_dt.date() - start_dt.date()).days > 90
    monthly_rollups: List[MonthlyRollupSummary] = []

    if is_rollup:
        monthly_map: Dict[str, List[Dict]] = {}
        for s in range_sessions:
            m_key = s.get("date", "")[:7]
            monthly_map.setdefault(m_key, []).append(s)

        for m_key in sorted(monthly_map.keys()):
            m_s = monthly_map[m_key]
            avg_c = sum(s["fluency_score"] for s in m_s) / len(m_s)
            avg_v = sum(s["vocabulary_score"] for s in m_s) / len(m_s)
            tot_t = sum(s.get("duration_seconds", 0) for s in m_s)
            monthly_rollups.append(
                MonthlyRollupSummary(
                    month=m_key,
                    sessions_count=len(m_s),
                    avg_confidence_score=round(avg_c, 2),
                    avg_vocabulary_score=round(avg_v, 2),
                    total_practice_seconds=tot_t,
                )
            )

    # Build confidence trend and vocabulary growth data points
    conf_trend = []
    vocab_growth = []
    tot_seconds = 0

    for s in range_sessions:
        # PII Protection: Redact transcripts if present
        raw_tr = s.get("transcript") or ""
        clean_tr, _ = pii.redact(raw_tr)

        conf_trend.append({"date": s["date"], "score": s["fluency_score"]})
        vocab_growth.append({"date": s["date"], "score": s["vocabulary_score"]})
        tot_seconds += s.get("duration_seconds", 0)

    # Get earned badges in this range
    all_badges = await kv_store.store.list_values(BADGES_NS)
    range_badges = [
        b["badge_id"]
        for b in all_badges
        if b.get("user_id") == user_id
        and b.get("earned_at", "")[:10] >= payload.start_date
        and b.get("earned_at", "")[:10] <= payload.end_date
    ]

    return ProgressReportResponse(
        start_date=payload.start_date,
        end_date=payload.end_date,
        session_count=len(range_sessions),
        confidence_score_trend=conf_trend,
        vocabulary_growth=vocab_growth,
        total_practice_time_seconds=tot_seconds,
        badges_earned=range_badges,
        is_rollup=is_rollup,
        monthly_rollups=monthly_rollups,
        note=note,
    )


# ── Piece 5: Streak Restore Appeal ───────────────────────────────────────────
async def submit_streak_appeal(
    payload: StreakAppealRequest, user_id: str
) -> StreakAppealResponse:
    break_dt = _parse_date(payload.date_of_break)
    now_dt = _now()

    # Rule 1: Reject appeals older than 14 days
    if (now_dt.date() - break_dt.date()).days > 14:
        raise InvalidSubmissionError(
            "Appeals cannot be submitted for streak breaks older than 14 days."
        )

    # Rule 2: Account abuse prevention — flag if >= 5 appeals in rolling 30 days
    all_appeals = await kv_store.store.list_values(APPEALS_NS)
    cutoff_30d = (now_dt - timedelta(days=30)).isoformat()
    recent_user_appeals = [
        a for a in all_appeals
        if a.get("user_id") == user_id and a.get("created_at", "") >= cutoff_30d
    ]

    appeal_id = f"app_{uuid.uuid4().hex[:12]}"

    if len(recent_user_appeals) >= 4:  # This would be the 5th appeal
        appeal_record = {
            "appeal_id": appeal_id,
            "user_id": user_id,
            "date_of_break": payload.date_of_break,
            "reason": payload.reason,
            "has_evidence": payload.has_evidence,
            "status": "flagged_for_manual_review",
            "created_at": now_dt.isoformat(),
        }
        await kv_store.store.create(APPEALS_NS, appeal_id, appeal_record)
        return StreakAppealResponse(
            appeal_id=appeal_id,
            status="flagged_for_manual_review",
            message="Account flagged for manual review due to multiple recent appeal submissions.",
        )

    # Rule 3: Branch on evidence
    if payload.has_evidence:
        state = await get_user_streak_state(user_id)
        state["current_streak"] += 1
        state["highest_streak"] = max(state["highest_streak"], state["current_streak"])
        await _save_user_streak_state(user_id, state)

        appeal_record = {
            "appeal_id": appeal_id,
            "user_id": user_id,
            "date_of_break": payload.date_of_break,
            "reason": payload.reason,
            "has_evidence": True,
            "status": "approved",
            "created_at": now_dt.isoformat(),
        }
        await kv_store.store.create(APPEALS_NS, appeal_id, appeal_record)
        return StreakAppealResponse(
            appeal_id=appeal_id,
            status="approved",
            message=f"Appeal approved based on provided evidence. Streak restored to {state['current_streak']}.",
            restored_streak=state["current_streak"],
        )
    else:
        appeal_record = {
            "appeal_id": appeal_id,
            "user_id": user_id,
            "date_of_break": payload.date_of_break,
            "reason": payload.reason,
            "has_evidence": False,
            "status": "declined",
            "created_at": now_dt.isoformat(),
        }
        await kv_store.store.create(APPEALS_NS, appeal_id, appeal_record)
        return StreakAppealResponse(
            appeal_id=appeal_id,
            status="declined",
            message="Appeal declined: supporting evidence is required to manually restore a streak.",
        )


# ── Piece 6: Historical Data Retention & Chart Performance ──────────────────
async def get_historical_data(
    time_range: str, user_id: str
) -> HistoricalDataResponse:
    valid_ranges = ["week", "month", "year", "all_time"]
    if time_range not in valid_ranges:
        raise InvalidSubmissionError(
            f"Invalid time_range '{time_range}'. Must be one of {valid_ranges}."
        )

    sessions = await get_user_sessions(user_id)

    if time_range in ["week", "month"]:
        # Raw session data points
        raw_pts = []
        for s in sessions:
            raw_pts.append(
                SessionDataPoint(
                    session_id=s["session_id"],
                    timestamp=s["timestamp"],
                    confidence_score=s["fluency_score"],
                    fluency_score=s["fluency_score"],
                    vocabulary_score=s["vocabulary_score"],
                    pronunciation_score=s.get("pronunciation_score"),
                    duration_seconds=s.get("duration_seconds", 0),
                    is_outlier=s.get("fluency_score", 0) > 90 or s.get("fluency_score", 0) < 30,
                )
            )
        return HistoricalDataResponse(
            time_range=time_range,
            aggregation_level="raw",
            raw_sessions=raw_pts,
        )
    else:
        # Long-range aggregations ("year" -> weekly, "all_time" -> monthly)
        agg_level = "weekly" if time_range == "year" else "monthly"
        bucket_map: Dict[str, List[Dict]] = {}

        for s in sessions:
            s_dt = _parse_date(s.get("date", _today_str()))
            if agg_level == "weekly":
                b_key = f"{s_dt.year}-W{s_dt.isocalendar()[1]:02d}"
            else:
                b_key = s_dt.strftime("%Y-%m")
            bucket_map.setdefault(b_key, []).append(s)

        aggregated_pts = []
        for b_key in sorted(bucket_map.keys()):
            b_sessions = bucket_map[b_key]

            # Calculate metrics
            avg_c = sum(s["fluency_score"] for s in b_sessions) / len(b_sessions)
            avg_v = sum(s["vocabulary_score"] for s in b_sessions) / len(b_sessions)
            tot_time = sum(s.get("duration_seconds", 0) for s in b_sessions)

            # Preserve best outlier session in this bucket
            best_s = max(b_sessions, key=lambda x: x["fluency_score"])
            best_outlier_pt = SessionDataPoint(
                session_id=best_s["session_id"],
                timestamp=best_s["timestamp"],
                confidence_score=best_s["fluency_score"],
                fluency_score=best_s["fluency_score"],
                vocabulary_score=best_s["vocabulary_score"],
                pronunciation_score=best_s.get("pronunciation_score"),
                duration_seconds=best_s.get("duration_seconds", 0),
                is_outlier=True,
            )

            aggregated_pts.append(
                AggregatedDataPoint(
                    period_label=b_key,
                    start_date=b_sessions[0]["date"],
                    end_date=b_sessions[-1]["date"],
                    session_count=len(b_sessions),
                    avg_confidence=round(avg_c, 2),
                    avg_vocabulary=round(avg_v, 2),
                    total_practice_seconds=tot_time,
                    best_outlier_session=best_outlier_pt,
                    is_gap=False,
                )
            )

        return HistoricalDataResponse(
            time_range=time_range,
            aggregation_level=agg_level,
            aggregated_points=aggregated_pts,
        )


async def expand_period_data(period_label: str, user_id: str) -> ExpandDataPointResponse:
    sessions = await get_user_sessions(user_id)
    matched = []

    for s in sessions:
        s_dt = _parse_date(s.get("date", _today_str()))
        if "-W" in period_label:
            b_key = f"{s_dt.year}-W{s_dt.isocalendar()[1]:02d}"
        else:
            b_key = s_dt.strftime("%Y-%m")

        if b_key == period_label:
            matched.append(
                SessionDataPoint(
                    session_id=s["session_id"],
                    timestamp=s["timestamp"],
                    confidence_score=s["fluency_score"],
                    fluency_score=s["fluency_score"],
                    vocabulary_score=s["vocabulary_score"],
                    pronunciation_score=s.get("pronunciation_score"),
                    duration_seconds=s.get("duration_seconds", 0),
                )
            )

    return ExpandDataPointResponse(
        period_label=period_label,
        sessions=matched,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Full time-series dashboard (PDG-US-10/14) + legacy overview payload (PDG-US-14)
# ─────────────────────────────────────────────────────────────────────────────

async def _is_db_connected() -> bool:
    try:
        return db.is_connected()
    except Exception:
        return False


def _validate_score(score: Optional[float]) -> Tuple[Optional[float], bool]:
    """
    E-03 Corrupted Session Data Check:
    Validates a score. If score is out of bounds (< 0 or > 100), drops it (returns None)
    and flags it as an outlier.
    """
    if score is None:
        return None, False
    try:
        val = float(score)
        if val < 0.0 or val > 100.0:
            return None, True  # Outlier dropped!
        return round(val, 2), False
    except (ValueError, TypeError):
        return None, True


async def _flag_outlier_row(prisma_model, row_id: str, flag_field: str, offending_fields: List[str]) -> None:
    """
    E-03 (continued): actually persists the outlier flag onto the source row instead of
    only counting it in-memory, so the flagged session is visible for review later
    (appends rather than overwrites, since a row could be flagged more than once).
    """
    try:
        current = await prisma_model.find_unique(where={"id": row_id})
        if not current:
            return
        existing = list(getattr(current, flag_field) or [])
        existing.append({
            "type": "outlier_score",
            "fields": offending_fields,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
            "note": "Score outside the valid 0-100 range; dropped from progress dashboard aggregates.",
        })
        await prisma_model.update(where={"id": row_id}, data={flag_field: Json(existing)})
    except Exception as e:
        logger.warning(f"Failed to persist outlier flag ({flag_field}) on row {row_id}: {e}")


async def get_daily_streak_days(user_id: str) -> int:
    """The learner's Daily Challenge streak — read from the ONE source of truth.

    PDG-US-11 owns streaks (services/daily_challenge_service, kv-backed qualified_dates)
    and the Daily Challenge card / navbar icon render that number. This dashboard used to
    derive its own streak from a rolling 24-48h window over session rows, which answered a
    different question and showed the user a different number for the same word on the
    same screen. Reading the canonical value keeps the platform consistent.

    Best-effort: a streak lookup failure must never take down the whole dashboard.
    """
    try:
        from services import daily_challenge_service

        raw = await daily_challenge_service._get_streak_raw(user_id)
        _completed_today, alive_streak = daily_challenge_service._streak_view(
            raw, datetime.now(timezone.utc).date()
        )
        return alive_streak
    except Exception as e:
        logger.warning(f"Daily streak lookup failed: {e}")
        return 0


async def _fetch_completed_records_from_db(user_id: str) -> Tuple[List[Dict], int]:
    """
    Fetches completed session records across all module tables in DB,
    applying E-03 outlier score validation.
    """
    records: List[Dict] = []
    outliers_count = 0

    if not await _is_db_connected():
        return records, outliers_count

    # 1. BaselineAssessment
    try:
        baselines = await db.baselineassessment.find_many(
            where={"userId": user_id, "completedAt": {"not": None}}
        )
        for b in baselines:
            v_score, o1 = _validate_score(b.vocabularyScore)
            c_score, o2 = _validate_score(b.confidenceScore)
            f_score, o3 = _validate_score(b.fluencyScore)
            p_score, o4 = _validate_score(b.pronunciationScore)
            if any([o1, o2, o3, o4]):
                outliers_count += 1
                offending = [f for f, flagged in [
                    ("vocabulary_score", o1), ("confidence_score", o2),
                    ("fluency_score", o3), ("pronunciation_score", o4),
                ] if flagged]
                await _flag_outlier_row(db.baselineassessment, b.id, "outlierFlags", offending)

            dur = (b.completedAt - b.startedAt).total_seconds() if b.startedAt and b.completedAt else 60.0
            records.append({
                "source": "baseline",
                "completed_at": b.completedAt,
                "confidence_score": c_score,
                "fluency_score": f_score,
                "vocabulary_score": v_score,
                "pronunciation_score": p_score,
                "duration_seconds": max(0.0, dur),
            })
    except Exception as e:
        logger.warning(f"BaselineAssessment query failed: {e}")

    # 2. CoachingSession
    try:
        coaching = await db.coachingsession.find_many(
            where={"userId": user_id, "completedAt": {"not": None}}
        )
        for c in coaching:
            v_score, o1 = _validate_score(c.vocabularyScore)
            c_score, o2 = _validate_score(c.confidenceScore)
            f_score, o3 = _validate_score(c.fluencyScore)
            p_score, o4 = _validate_score(c.pronunciationScore)
            if any([o1, o2, o3, o4]):
                outliers_count += 1
                offending = [f for f, flagged in [
                    ("vocabulary_score", o1), ("confidence_score", o2),
                    ("fluency_score", o3), ("pronunciation_score", o4),
                ] if flagged]
                await _flag_outlier_row(db.coachingsession, c.id, "flags", offending)

            dur = (c.completedAt - c.createdAt).total_seconds() if c.createdAt and c.completedAt else 60.0
            records.append({
                "source": "coaching",
                "completed_at": c.completedAt,
                "confidence_score": c_score,
                "fluency_score": f_score,
                "vocabulary_score": v_score,
                "pronunciation_score": p_score,
                "duration_seconds": max(0.0, dur),
            })
    except Exception as e:
        logger.warning(f"CoachingSession query failed: {e}")

    # 3. ScenarioSession
    try:
        scenarios = await db.scenariosession.find_many(
            where={"userId": user_id, "completedAt": {"not": None}}
        )
        for s in scenarios:
            v_score, o1 = _validate_score(s.vocabularyScore)
            c_score, o2 = _validate_score(s.confidenceScore)
            if any([o1, o2]):
                outliers_count += 1
                offending = [f for f, flagged in [
                    ("vocabulary_score", o1), ("confidence_score", o2),
                ] if flagged]
                await _flag_outlier_row(db.scenariosession, s.id, "flags", offending)

            dur = (s.completedAt - s.createdAt).total_seconds() if s.createdAt and s.completedAt else 60.0
            records.append({
                "source": "scenario",
                "completed_at": s.completedAt,
                "confidence_score": c_score,
                "fluency_score": None,
                "vocabulary_score": v_score,
                "pronunciation_score": None,
                "duration_seconds": max(0.0, dur),
            })
    except Exception as e:
        logger.warning(f"ScenarioSession query failed: {e}")

    # 4. PublicSpeakingSession
    try:
        ps_sessions = await db.publicspeakingsession.find_many(
            where={"userId": user_id, "status": "completed"}
        )
        for ps in ps_sessions:
            scorecard = ps.scorecard or {}
            raw_conf = scorecard.get("confidence", scorecard.get("overall_score"))
            raw_pacing = scorecard.get("pacing")
            raw_clarity = scorecard.get("voice_clarity")

            c_score, o1 = _validate_score(raw_conf)
            f_score, o2 = _validate_score(raw_pacing)
            p_score, o3 = _validate_score(raw_clarity)
            if any([o1, o2, o3]):
                outliers_count += 1
                offending = [f for f, flagged in [
                    ("confidence_score", o1), ("fluency_score", o2), ("pronunciation_score", o3),
                ] if flagged]
                await _flag_outlier_row(db.publicspeakingsession, ps.id, "outlierFlags", offending)

            dur = (ps.completedAt - ps.createdAt).total_seconds() if ps.createdAt and ps.completedAt else 60.0
            records.append({
                "source": "public_speaking",
                "completed_at": ps.completedAt or ps.createdAt,
                "confidence_score": c_score,
                "fluency_score": f_score,
                "vocabulary_score": None,
                "pronunciation_score": p_score,
                "duration_seconds": max(0.0, dur),
            })
    except Exception as e:
        logger.warning(f"PublicSpeakingSession query failed: {e}")

    # Sort records ascending by completed_at
    records.sort(key=lambda r: r["completed_at"])
    return records, outliers_count


async def _vocabulary_growth_detail(user_id: str) -> Dict:
    """Vocabulary growth from ScenarioSession, with the words and the PDG-US-14
    empty/zero-growth messaging the legacy overview payload renders.

    Single implementation — _fetch_vocab_growth_count is just the count view of this,
    so the "new words since last session" rule lives in exactly one place.
    """
    empty = {
        "new_words_count": 0,
        "new_words": [],
        "is_empty_state": True,
        "is_zero_growth": False,
        "message": _EMPTY_STATE_MESSAGE,
    }
    if not await _is_db_connected():
        return empty

    try:
        sessions = await db.scenariosession.find_many(
            where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "asc"}
        )
        if not sessions:
            return empty

        seen: set = set()
        for session in sessions[:-1]:
            seen.update(session.vocabUsed or [])

        latest_new_words = sorted(set(sessions[-1].vocabUsed or []) - seen)
        # E-03: cap so a scoring anomaly can't skew the chart.
        new_words_count = min(len(latest_new_words), MAX_DAILY_VOCAB_GROWTH)
        is_zero_growth = new_words_count == 0
        return {
            "new_words_count": new_words_count,
            "new_words": latest_new_words[:MAX_DAILY_VOCAB_GROWTH],
            "is_empty_state": False,
            "is_zero_growth": is_zero_growth,
            "message": _ZERO_GROWTH_MESSAGE if is_zero_growth else None,
        }
    except Exception as e:
        logger.warning(f"Vocab growth query failed: {e}")
        return empty


async def _fetch_vocab_growth_count(user_id: str) -> int:
    """Fetch vocabulary growth count from ScenarioSession."""
    return (await _vocabulary_growth_detail(user_id))["new_words_count"]


def _build_dashboard_payload(
    user_id: str,
    records: List[Dict],
    outliers_count: int,
    vocab_growth_count: int,
    sync_status: str = "synced",
    is_stale: bool = False,
    sync_message: Optional[str] = None,
    lifetime_practice_seconds: float = 0.0,
    daily_streak_days: int = 0,
) -> Dict:
    """Constructs the complete ProgressDashboardResponseSchema dict."""
    now_str = datetime.now(timezone.utc).isoformat()

    # E-02: Empty state for Day 1 users with 0 completed sessions
    if not records:
        primary_metric = PrimaryMetricSchema(
            name="Confidence Score",
            value=0.0,
            unit="pts",
            is_primary=True,
            description="Your primary overall confidence indicator across all learning modules.",
        )
        summary = ProgressDashboardMetricsSchema(
            confidence_score=primary_metric,
            fluency_score=None,
            vocabulary_score=None,
            pronunciation_score=None,
            total_practice_time_minutes=0.0,
            total_practice_time_hours=0.0,
            completed_sessions_count=0,
            vocabulary_growth_count=0,
            daily_streak_days=0,
        )
        return ProgressDashboardResponseSchema(
            user_id=user_id,
            generated_at=now_str,
            sync_status=sync_status,
            is_stale=is_stale,
            is_empty_state=True,
            empty_state_prompt=DAY1_MOTIVATIONAL_PROMPT,
            primary_metric=primary_metric,
            summary_metrics=summary,
            trend_lines=[],
            flagged_outliers_count=outliers_count,
            sync_message=sync_message or DAY1_MOTIVATIONAL_PROMPT,
        ).model_dump()

    # Calculate latest valid metrics
    def _latest(key: str) -> Optional[float]:
        for r in reversed(records):
            if r.get(key) is not None:
                return r[key]
        return None

    latest_conf = _latest("confidence_score") or 0.0
    latest_fluency = _latest("fluency_score")
    latest_vocab = _latest("vocabulary_score")
    latest_pron = _latest("pronunciation_score")

    # Total practice time comes from the SAME source of truth as the Practice Time
    # Milestones panel (practice_time_service): the ping-credited lifetime total on the
    # user, not a sum of per-session wall-clock spans. Summing spans counts idle/menu
    # time and drifts out of step with the Trophy Case; the ping total already excludes
    # idle, stale and concurrent-device pings. Per-session spans below are untouched —
    # they still drive the per-point trend chart.
    total_seconds = lifetime_practice_seconds
    total_minutes = round(total_seconds / 60.0, 1)
    total_hours = round(total_seconds / 3600.0, 2)
    streak_days = daily_streak_days

    primary_metric = PrimaryMetricSchema(
        name="Confidence Score",
        value=latest_conf,
        unit="pts",
        is_primary=True,
        description="Your primary overall confidence indicator across all learning modules.",
    )

    summary = ProgressDashboardMetricsSchema(
        confidence_score=primary_metric,
        fluency_score=latest_fluency,
        vocabulary_score=latest_vocab,
        pronunciation_score=latest_pron,
        total_practice_time_minutes=total_minutes,
        total_practice_time_hours=total_hours,
        completed_sessions_count=len(records),
        vocabulary_growth_count=vocab_growth_count,
        daily_streak_days=streak_days,
    )

    # Build trend lines for visual charts
    trend_lines: List[TrendPointSchema] = []
    for r in records:
        d_str = r["completed_at"].isoformat() if hasattr(r["completed_at"], "isoformat") else str(r["completed_at"])
        p_min = round(r.get("duration_seconds", 0.0) / 60.0, 1)
        trend_lines.append(
            TrendPointSchema(
                date=d_str,
                confidence_score=r.get("confidence_score"),
                fluency_score=r.get("fluency_score"),
                vocabulary_score=r.get("vocabulary_score"),
                pronunciation_score=r.get("pronunciation_score"),
                practice_time_minutes=p_min,
            )
        )

    # Cap trend lines payload to recent 30 points
    trend_lines = trend_lines[-30:]

    return ProgressDashboardResponseSchema(
        user_id=user_id,
        generated_at=now_str,
        sync_status=sync_status,
        is_stale=is_stale,
        is_empty_state=False,
        empty_state_prompt=None,
        primary_metric=primary_metric,
        summary_metrics=summary,
        trend_lines=trend_lines,
        flagged_outliers_count=outliers_count,
        sync_message=sync_message,
    ).model_dump()


async def get_progress_dashboard(user_id: str = Depends(require_auth)) -> Dict:
    """
    Main API Handler for GET /api/progress-dashboard/progress.
    Fetches real-time metrics across all session models.
    Handles E-01 DB failure with last-known-good snapshot fallback.
    """
    try:
        # Check KV store for seeded / simulated session records during test runs
        kv_records = await kv_store.store.get("test_dashboard_records", user_id)
        if kv_records and isinstance(kv_records, list):
            db_records = kv_records
            outliers_count = 0
            # Apply E-03 validation to test records
            clean_records = []
            for r in db_records:
                c_score, o1 = _validate_score(r.get("confidence_score"))
                f_score, o2 = _validate_score(r.get("fluency_score"))
                v_score, o3 = _validate_score(r.get("vocabulary_score"))
                p_score, o4 = _validate_score(r.get("pronunciation_score"))
                if any([o1, o2, o3, o4]):
                    outliers_count += 1
                r_clean = dict(r)
                r_clean["confidence_score"] = c_score
                r_clean["fluency_score"] = f_score
                r_clean["vocabulary_score"] = v_score
                r_clean["pronunciation_score"] = p_score
                clean_records.append(r_clean)
            db_records = clean_records
        else:
            db_records, outliers_count = await _fetch_completed_records_from_db(user_id)

        vocab_growth = await _fetch_vocab_growth_count(user_id)
        # Single source of truth for practice time — see _build_dashboard_payload.
        dashboard_user = await db.user.find_unique(where={"id": user_id})
        payload = _build_dashboard_payload(
            user_id,
            db_records,
            outliers_count,
            vocab_growth,
            lifetime_practice_seconds=(dashboard_user.lifetimePracticeSeconds if dashboard_user else 0.0),
            daily_streak_days=await get_daily_streak_days(user_id),
        )

        # E-01: Save last-known-good snapshot to KV store. create() fails with a
        # unique-constraint violation once a snapshot row already exists for this
        # user, so update the existing row instead of always creating.
        existing_snapshot = await kv_store.store.get(DASHBOARD_SNAPSHOT_NS, user_id)
        if existing_snapshot is None:
            await kv_store.store.create(DASHBOARD_SNAPSHOT_NS, user_id, payload)
        else:
            await kv_store.store.update(DASHBOARD_SNAPSHOT_NS, user_id, payload)
        return payload

    except Exception as exc:
        logger.error(f"Error building progress dashboard for user {user_id}: {exc}")
        # E-01 Fallback: fetch last known good snapshot from KV store
        snapshot = await kv_store.store.get(DASHBOARD_SNAPSHOT_NS, user_id)
        if snapshot and isinstance(snapshot, dict):
            snapshot["sync_status"] = "stale"
            snapshot["is_stale"] = True
            snapshot["sync_message"] = SYNC_STALE_MESSAGE
            return snapshot

        # If no snapshot exists, return zero-state payload with stale flag
        return _build_dashboard_payload(
            user_id,
            records=[],
            outliers_count=0,
            vocab_growth_count=0,
            sync_status="stale",
            is_stale=True,
            sync_message=SYNC_STALE_MESSAGE,
        )


async def get_overview(user_id: str = Depends(require_auth)):
    """Backwards-compatible endpoint for existing UI / tests.

    Returns the flat legacy shape the Vocabulary Growth panel reads
    (has_data / metrics / vocabulary_growth / vocabulary_history). The richer
    time-series payload lives on /progress and /track via get_progress_dashboard —
    this deliberately does NOT delegate to it, because that response has a different
    schema and would break the existing panel.
    """
    from services.gating_service import GatedFeature, check_feature_access

    access = await check_feature_access(user_id, GatedFeature.PROGRESS_DASHBOARD.value)
    if not access["accessible"]:
        return JSONResponse(status_code=403, content={"error": access["reason"], "gating": access})

    records, _outliers = await _fetch_completed_records_from_db(user_id)
    records.sort(key=lambda r: r["completed_at"])
    growth = await _vocabulary_growth_detail(user_id)

    # Same single source of truth for practice time as the Milestones panel.
    user = await db.user.find_unique(where={"id": user_id})
    practice_time_minutes = round((user.lifetimePracticeSeconds if user else 0.0) / 60, 1)

    def _latest(key: str) -> Optional[float]:
        for record in reversed(records):
            value = record.get(key)
            if value is not None:
                return round(value, 2)
        return None

    vocabulary_history = [
        {"date": r["completed_at"].isoformat(), "vocabulary_score": round(r["vocabulary_score"], 2)}
        for r in records
        if r.get("vocabulary_score") is not None
    ][-20:]  # cap chart payload to the most recent 20 points

    return {
        "has_data": bool(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "practice_time_minutes": practice_time_minutes,
            "confidence_score": _latest("confidence_score"),
            "fluency_score": _latest("fluency_score"),
            "vocabulary_score": _latest("vocabulary_score"),
        },
        "vocabulary_growth": growth,
        "vocabulary_history": vocabulary_history,
    }
