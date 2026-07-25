import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from lib import confidence_engine, kv_store, pii
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
    ProgressReportRequest,
    ProgressReportResponse,
    SessionDataPoint,
    StreakAppealRequest,
    StreakAppealResponse,
    StreakInfoResponse,
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
