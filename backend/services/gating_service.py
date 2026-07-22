"""
Skip Assessment & Feature-Access Gating.

Rewritten against the User/PromptLog rows instead of InMemoryStorage's in-memory
skip_prompt_history dict. The enterprise-mandatory-assessment branch
(`_check_enterprise_mandatory_policy`, hardcoded to always return False in
the source) is dropped — there's no organization/enterprise data anywhere
in this codebase to back it.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict

from fastapi import Depends
from fastapi.responses import JSONResponse

from lib.prisma_client import db
from middlewares.auth_middleware import require_auth
from prisma.enums import AssessmentStatus, PromptKind

logger = logging.getLogger(__name__)


class FeatureAccessLevel(str, Enum):
    FULL_ACCESS = "full_access"
    ASSESSMENT_REQUIRED = "assessment_required"
    BASIC_ONLY = "basic_only"


class GatedFeature(str, Enum):
    AI_CONVERSATION_PRACTICE = "ai_conversation_practice"
    INTERVIEW_COACH = "interview_coach"
    SCENARIO_BASED_LEARNING = "scenario_based_learning"
    WORKPLACE_ENGLISH_COACH = "workplace_english_coach"
    PROGRESS_DASHBOARD = "progress_dashboard"
    LEARNING_PATHS = "learning_paths"
    DAILY_CHALLENGES = "daily_challenges"
    MOCK_INTERVIEWS = "mock_interviews"


class BasicFeature(str, Enum):
    ACCOUNT_SETTINGS = "account_settings"
    PROFILE_MANAGEMENT = "profile_management"
    HELP_DOCUMENTATION = "help_documentation"
    ASSESSMENT_INTRO = "assessment_intro"


GATED_FEATURE_LABELS = {
    GatedFeature.AI_CONVERSATION_PRACTICE: "AI Conversation Practice",
    GatedFeature.INTERVIEW_COACH: "Interview Coach",
    GatedFeature.SCENARIO_BASED_LEARNING: "Scenario-Based Learning",
    GatedFeature.WORKPLACE_ENGLISH_COACH: "Workplace English Coach",
    GatedFeature.PROGRESS_DASHBOARD: "Progress Dashboard",
    GatedFeature.LEARNING_PATHS: "Learning Paths",
    GatedFeature.DAILY_CHALLENGES: "Daily Challenges",
    GatedFeature.MOCK_INTERVIEWS: "Mock Interviews",
}

SKIP_ESCALATION_THRESHOLD = 3


async def get_access_level(user_id: str) -> FeatureAccessLevel:
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return FeatureAccessLevel.ASSESSMENT_REQUIRED
    if user.assessmentStatus == AssessmentStatus.COMPLETED:
        return FeatureAccessLevel.FULL_ACCESS
    elif user.assessmentStatus == AssessmentStatus.UNASSESSED:
        return FeatureAccessLevel.BASIC_ONLY
    return FeatureAccessLevel.ASSESSMENT_REQUIRED


async def check_feature_access(user_id: str, feature: str) -> Dict:
    access_level = await get_access_level(user_id)

    try:
        BasicFeature(feature)
        return {
            "accessible": True,
            "feature": feature,
            "access_level": access_level.value,
            "reason": "Basic feature always available",
        }
    except ValueError:
        pass

    try:
        gated_feature = GatedFeature(feature)
        if access_level == FeatureAccessLevel.FULL_ACCESS:
            return {
                "accessible": True,
                "feature": feature,
                "access_level": access_level.value,
                "reason": "Assessment completed",
            }
        return {
            "accessible": False,
            "feature": feature,
            "access_level": access_level.value,
            "reason": "Assessment required to unlock this feature",
            "feature_name": GATED_FEATURE_LABELS[gated_feature],
        }
    except ValueError:
        pass

    return {
        "accessible": True,
        "feature": feature,
        "access_level": access_level.value,
        "reason": "Unknown feature, allowing access",
    }


def _locked_message(access_level: FeatureAccessLevel) -> str:
    if access_level == FeatureAccessLevel.BASIC_ONLY:
        return "Complete the baseline assessment to unlock personalized coaching features."
    return "Assessment in progress. Complete it to access all features."


async def get_accessible_features(user_id: str) -> Dict:
    access_level = await get_access_level(user_id)

    if access_level == FeatureAccessLevel.FULL_ACCESS:
        return {
            "access_level": access_level.value,
            "accessible_features": [f.value for f in GatedFeature] + [f.value for f in BasicFeature],
            "inaccessible_features": [],
        }

    return {
        "access_level": access_level.value,
        "accessible_features": [f.value for f in BasicFeature],
        "inaccessible_features": [f.value for f in GatedFeature],
        "locked_message": _locked_message(access_level),
    }


async def _skip_prompt_count(user_id: str) -> int:
    return await db.promptlog.count(where={"userId": user_id, "kind": PromptKind.SKIP_ASSESSMENT})


def _assessment_prompt_message(prompt_count: int) -> str:
    if prompt_count == 0:
        return "Complete your baseline assessment to unlock personalized learning features."
    elif prompt_count == 1:
        return "Your assessment is still pending. Complete it to access AI Conversation Practice and other features."
    elif prompt_count == 2:
        return "You still haven't completed the assessment. Unlock all features by spending 5 minutes on the baseline evaluation."
    return f"You've skipped the assessment {prompt_count} times. Complete it now to access the full learning experience."


async def should_show_assessment_prompt(user_id: str) -> bool:
    user = await db.user.find_unique(where={"id": user_id})
    if not user or user.assessmentStatus != AssessmentStatus.UNASSESSED:
        return False

    last_prompt = await db.promptlog.find_first(
        where={"userId": user_id, "kind": PromptKind.SKIP_ASSESSMENT}, order={"createdAt": "desc"}
    )
    if not last_prompt:
        return True
    return datetime.now(timezone.utc) - last_prompt.createdAt >= timedelta(hours=1)


# ── Controllers ───────────────────────────────────────────────────────────────
async def get_user_feature_summary(user_id: str = Depends(require_auth)):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    access_level = await get_access_level(user_id)
    features = await get_accessible_features(user_id)
    show_prompt = await should_show_assessment_prompt(user_id)
    prompt_count = await _skip_prompt_count(user_id)

    return {
        "user_id": user_id,
        "display_name": user.name or user.email,
        "assessment_status": user.assessmentStatus,
        "access_level": access_level.value,
        "skip_prompt_count": prompt_count,
        "show_assessment_prompt": show_prompt,
        "assessment_prompt_message": _assessment_prompt_message(prompt_count) if show_prompt else None,
        "accessible_features": features["accessible_features"],
        "inaccessible_features": features.get("inaccessible_features", []),
        "locked_message": features.get("locked_message"),
    }


async def attempt_skip_assessment(user_id: str = Depends(require_auth)):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    prompt_count = await _skip_prompt_count(user_id)
    if prompt_count >= SKIP_ESCALATION_THRESHOLD:
        return {
            "success": False,
            "reason": "Repeated skip attempts",
            "can_skip": True,
            "escalated": True,
            "message": (
                f"You've skipped the assessment {prompt_count} times. "
                "Without it, you cannot access AI Conversation Practice, Interview Coach, "
                "or Scenario-Based Learning. Complete the assessment to unlock all features."
            ),
        }

    return {
        "success": True,
        "action_required": "confirm_skip",
        "can_skip": True,
        "message": (
            "All coaching features require a baseline score to personalize your practice. "
            "Without the assessment, AI Conversation Practice, Interview Coach, and "
            "Scenario-Based Learning will be locked. You can complete the assessment later."
        ),
        "skip_count": prompt_count,
    }


async def confirm_skip_assessment(user_id: str = Depends(require_auth)):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    await db.user.update(where={"id": user_id}, data={"assessmentStatus": AssessmentStatus.UNASSESSED})
    await db.promptlog.create(data={"userId": user_id, "kind": PromptKind.SKIP_ASSESSMENT})

    return {
        "success": True,
        "status": "unassessed",
        "message": "Assessment skipped. Complete it later to unlock all features.",
        "accessible_features": await get_accessible_features(user_id),
    }
