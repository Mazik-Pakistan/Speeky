"""
Periodic Baseline Re-Assessment

Wired together here so `start_re_assessment(is_early=True)` actually enforces the 7-day cooldown
and one-early-retake-per-cycle rule instead of that logic being dead.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from fastapi import Depends
from fastapi.responses import JSONResponse

from lib.prisma_client import db
from middlewares.auth_middleware import require_auth
from prisma.enums import AssessmentStatus, PromptKind

logger = logging.getLogger(__name__)

CYCLE_DAYS = 30
EARLY_RETAKE_COOLDOWN_DAYS = 7
REGRESSION_THRESHOLD = 15.0
STAGNATION_MIN_CYCLES = 3
STAGNATION_VARIANCE_THRESHOLD = 5.0


def _prompt_message(prompt_type: str) -> Tuple[str, str]:
    if prompt_type == "scheduled":
        return (
            "Time for your Monthly Check-in! Complete your re-assessment to track your "
            "progress and recalibrate your learning level.",
            "normal",
        )
    elif prompt_type == "early":
        return (
            "You're eligible for an early re-assessment. Check your progress before the "
            "scheduled 30-day cycle.",
            "low",
        )
    elif prompt_type == "regression_detected":
        return "Your recent score was unusually low. Would you like to retake the assessment to ensure accuracy?", "high"
    return "Complete your re-assessment to track your progress.", "normal"


async def check_eligibility(user_id: str) -> Dict:
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return {"is_eligible": False, "reason": "User not found"}
    if user.assessmentStatus != AssessmentStatus.COMPLETED:
        return {"is_eligible": False, "reason": "Initial assessment not completed"}

    last = await db.baselineassessment.find_first(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "desc"}
    )
    if not last:
        return {"is_eligible": False, "reason": "No completed assessment found"}

    days_since = (datetime.now(timezone.utc) - last.completedAt).days
    if days_since >= CYCLE_DAYS:
        return {
            "is_eligible": True,
            "last_assessment_date": last.completedAt.isoformat(),
            "scheduled_date": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "is_eligible": False,
        "days_until_eligible": CYCLE_DAYS - days_since,
        "reason": f"Cycle not complete. {CYCLE_DAYS - days_since} days remaining.",
        "last_assessment_date": last.completedAt.isoformat(),
        "scheduled_date": (last.completedAt + timedelta(days=CYCLE_DAYS)).isoformat(),
    }


async def _current_cycle_number(user_id: str) -> int:
    first = await db.baselineassessment.find_first(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "asc"}
    )
    if not first or not first.completedAt:
        return 0
    days_since = (datetime.now(timezone.utc) - first.completedAt).days
    return days_since // CYCLE_DAYS + 1


async def _check_early_retake_eligibility(user_id: str) -> Tuple[bool, Optional[str]]:
    last = await db.baselineassessment.find_first(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "desc"}
    )
    if not last:
        return False, "No completed assessment found"

    days_since = (datetime.now(timezone.utc) - last.completedAt).days
    if days_since < EARLY_RETAKE_COOLDOWN_DAYS:
        return False, f"Early retake not eligible. {EARLY_RETAKE_COOLDOWN_DAYS - days_since} days remaining."

    cycle = await _current_cycle_number(user_id)
    early_count = await db.reassessmentrequest.count(
        where={"userId": user_id, "isEarlyRetake": True, "cycleCount": cycle}
    )
    if early_count >= 1:
        return False, "Already used early retake for this cycle."

    return True, None


async def should_show_prompt(user_id: str) -> bool:
    eligibility = await check_eligibility(user_id)
    if not eligibility["is_eligible"]:
        return False

    last_prompt = await db.promptlog.find_first(
        where={"userId": user_id, "kind": PromptKind.REASSESSMENT}, order={"createdAt": "desc"}
    )
    if last_prompt and datetime.now(timezone.utc) - last_prompt.createdAt < timedelta(hours=24):
        return False
    return True


async def check_stagnation(user_id: str, min_cycles: int = STAGNATION_MIN_CYCLES) -> bool:
    """Flag a plateaued user (BAS-US-12) — no caller in the source, wired
    in here at the natural per-request point that already reads history."""
    assessments = await db.baselineassessment.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "asc"}
    )
    if len(assessments) < min_cycles:
        return False

    scores = [a.confidenceScore for a in assessments[-min_cycles:] if a.confidenceScore is not None]
    if len(scores) < min_cycles:
        return False

    is_plateaued = (max(scores) - min(scores)) < STAGNATION_VARIANCE_THRESHOLD
    if is_plateaued:
        await db.user.update(where={"id": user_id}, data={"assessmentStatus": AssessmentStatus.PLATEAUED})
    return is_plateaued


async def get_progress_trend(user_id: str) -> Dict:
    assessments = await db.baselineassessment.find_many(
        where={"userId": user_id, "completedAt": {"not": None}}, order={"completedAt": "asc"}
    )
    if len(assessments) < 2:
        return {"has_trend_data": False, "reason": "Need at least 2 completed assessments for trend analysis"}

    trend_data = [
        {
            "date": a.completedAt.isoformat(),
            "confidence_score": a.confidenceScore,
            "fluency_score": a.fluencyScore,
            "vocabulary_score": a.vocabularyScore,
            "pronunciation_score": a.pronunciationScore,
            "learning_level": a.learningLevel,
        }
        for a in assessments
    ]

    first_score = trend_data[0]["confidence_score"]
    last_score = trend_data[-1]["confidence_score"]
    overall_change = last_score - first_score

    days_span = (assessments[-1].completedAt - assessments[0].completedAt).days
    avg_rate = overall_change / days_span if days_span > 0 else 0

    return {
        "has_trend_data": True,
        "assessment_count": len(trend_data),
        "trend_data": trend_data,
        "overall_change": overall_change,
        "average_rate_per_day": avg_rate,
        "current_score": last_score,
        "starting_score": first_score,
        "trend_direction": "improving" if overall_change > 0 else "declining" if overall_change < 0 else "stable",
    }


async def detect_score_regression(
    user_id: str, new_score: float, exclude_assessment_id: Optional[str] = None
) -> Dict:
    where = {"userId": user_id, "completedAt": {"not": None}}
    if exclude_assessment_id:
        where["id"] = {"not": exclude_assessment_id}

    previous = await db.baselineassessment.find_first(where=where, order={"completedAt": "desc"})
    if not previous or previous.confidenceScore is None:
        return {"regression_detected": False, "reason": "No previous assessment for comparison"}

    previous_score = previous.confidenceScore
    score_drop = previous_score - new_score

    if score_drop >= REGRESSION_THRESHOLD:
        return {
            "regression_detected": True,
            "previous_score": previous_score,
            "new_score": new_score,
            "score_drop": score_drop,
            "reason": f"Score dropped by {score_drop:.1f} points from previous assessment",
        }
    return {
        "regression_detected": False,
        "previous_score": previous_score,
        "new_score": new_score,
        "score_change": new_score - previous_score,
        "reason": "No significant regression detected",
    }


def handle_regression_flag(regression_data: Dict) -> Dict:
    if not regression_data.get("regression_detected"):
        return {"action": "none", "reason": "No regression detected"}

    message, urgency = _prompt_message("regression_detected")
    return {
        "action": "prompt_retake",
        "prompt": {
            "message": message,
            "urgency": urgency,
            "previous_score": regression_data["previous_score"],
            "new_score": regression_data["new_score"],
            "score_drop": regression_data["score_drop"],
        },
        "options": ["retake_assessment", "accept_score", "contact_support"],
    }


# ── Controllers ───────────────────────────────────────────────────────────────
async def get_re_assessment_summary(user_id: str = Depends(require_auth)):
    eligibility = await check_eligibility(user_id)
    await check_stagnation(user_id)
    progress_trend = await get_progress_trend(user_id)
    show_prompt = await should_show_prompt(user_id)

    prompt = None
    if show_prompt:
        message, urgency = _prompt_message("scheduled")
        prompt = {"message": message, "urgency": urgency}

    return {
        "user_id": user_id,
        "eligibility": eligibility,
        "should_show_prompt": show_prompt,
        "prompt": prompt,
        "progress_trend": progress_trend,
        "configuration": {
            "cycle_days": CYCLE_DAYS,
            "early_retake_cooldown_days": EARLY_RETAKE_COOLDOWN_DAYS,
            "regression_threshold": REGRESSION_THRESHOLD,
        },
    }


async def start_re_assessment(is_early: bool = False, user_id: str = Depends(require_auth)):
    if is_early:
        ok, reason = await _check_early_retake_eligibility(user_id)
        if not ok:
            return JSONResponse(status_code=400, content={"error": reason})
    else:
        eligibility = await check_eligibility(user_id)
        if not eligibility["is_eligible"]:
            return JSONResponse(
                status_code=400,
                content={"error": eligibility.get("reason"), "days_until_eligible": eligibility.get("days_until_eligible")},
            )

    cycle = await _current_cycle_number(user_id)
    await db.reassessmentrequest.create(
        data={"userId": user_id, "isEarlyRetake": is_early, "cycleCount": cycle}
    )

    from services import assessment_service

    # _begin_assessment, not start_assessment: eligibility/cooldown is already enforced
    # above, and start_assessment's "baseline already completed" guard would reject every
    # re-assessment (the user has, by definition, a completed baseline).
    result = await assessment_service._begin_assessment(user_id)
    if isinstance(result, JSONResponse):
        return result
    result["is_re_assessment"] = True
    return result


async def dismiss_prompt(user_id: str = Depends(require_auth), dismiss_duration_hours: int = 24):
    eligibility = await check_eligibility(user_id)
    if not eligibility["is_eligible"]:
        return JSONResponse(status_code=400, content={"error": "Not eligible for re-assessment"})

    await db.promptlog.create(data={"userId": user_id, "kind": PromptKind.REASSESSMENT})
    dismiss_until = datetime.now(timezone.utc) + timedelta(hours=dismiss_duration_hours)

    return {
        "success": True,
        "dismissed_until": dismiss_until.isoformat(),
        "message": f"Prompt dismissed. You'll be reminded again after {dismiss_duration_hours} hours.",
    }
