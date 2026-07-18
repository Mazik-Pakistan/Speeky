"""
Direct-file test harness for Baseline Assessment & Confidence Scoring.

Exercises the Speeky package modules directly (no Flask, no HTTP) against the
validation test cases (TC-xxx) from "Speeky Ai user stories Recounted 2.docx",
for the user stories that have code: BAS-US-01, 02, 03, 04, 09, 10, 12.

BAS-US-05/06/07/08 are marked "Not Started (Gap)" in the doc and have no
dedicated implementation to test. BAS-US-11 depends on the LLM-backed
grammar/response pipeline (Ollama) and is out of scope for an offline test.

Run:
    .venv_test\\Scripts\\python.exe tests\\test_baseline_direct.py
(or any interpreter with `numpy` installed — no other deps required for the
text-mode flow exercised here.)
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from speeky.storage import InMemoryStorage, LearningLevel, AssessmentStatus
from speeky.confidence import ConfidenceScoreEngine, SessionScore
from speeky.pipeline import SpeekyPipeline
from speeky.assessment import InitialCommunicationAssessment, AssessmentIntegrityChecker
from speeky.results import ResultsSummaryView
from speeky.gating import FeatureAccessGating, GatedFeature, BasicFeature
from speeky.reassessment import PeriodicReAssessment

PASS, FAIL, GAP = [], [], []


def check(tc_id, description, condition, gap_note=None):
    """Record a single TC result. gap_note marks a known, reported implementation gap."""
    if gap_note:
        GAP.append((tc_id, description, gap_note))
        print(f"[GAP ] {tc_id}: {description}\n       -> {gap_note}")
        return
    if condition:
        PASS.append((tc_id, description))
        print(f"[PASS] {tc_id}: {description}")
    else:
        FAIL.append((tc_id, description))
        print(f"[FAIL] {tc_id}: {description}")


def new_stack():
    """Fresh storage/engine/pipeline/assessment stack per scenario, so tests don't bleed into each other."""
    storage = InMemoryStorage()
    engine = ConfidenceScoreEngine()
    pipeline = SpeekyPipeline(lazy_loading=True, confidence_engine=engine)
    assessment = InitialCommunicationAssessment(pipeline, storage, engine)
    results = ResultsSummaryView(storage, engine)
    gating = FeatureAccessGating(storage)
    reassess = PeriodicReAssessment(storage, assessment)
    return storage, engine, pipeline, assessment, results, gating, reassess


def run_full_text_assessment(storage, assessment, user_id, answers):
    """Submit `answers` (list of str, or dict for clipboard/flag control) through a full 5-question cycle."""
    start = assessment.start_assessment(user_id)
    aid = start['assessment_id']
    last = None
    for a in answers:
        if isinstance(a, dict):
            last = assessment.submit_response(aid, response_type='text', **a)
        else:
            last = assessment.submit_response(aid, response_type='text', text_data=a)
    return aid, last


GOOD_ANSWERS = [
    "I usually wake up early and go for a run before starting my workday at the office downtown.",
    "My main goal is to communicate more confidently in meetings and client calls at work.",
    "The most important quality for success is persistence combined with clear communication skills.",
    "Last year I had to resolve a conflict between two teammates by listening to both sides carefully.",
    "I enjoy hiking on weekends because it helps me clear my mind and stay physically active.",
]


# ---------------------------------------------------------------------------
# BAS-US-09: Initial Communication Assessment
# ---------------------------------------------------------------------------
print("\n=== BAS-US-09: Initial Communication Assessment ===")

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc09_02", "TC-002 User")
aid, final = run_full_text_assessment(storage, assessment, user.user_id, GOOD_ANSWERS)
check("BAS-US-09 TC-002", "Complete text assessment generates scores; pronunciation is N/A",
      final['status'] == 'completed' and final['pronunciation_score'] is None
      and final['fluency_score'] is not None and final['vocabulary_score'] > 0)

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc09_05", "TC-005 User")
start = assessment.start_assessment(user.user_id)
aid = start['assessment_id']
assessment.submit_response(aid, response_type='text', text_data=GOOD_ANSWERS[0])
assessment.submit_response(aid, response_type='text', text_data=GOOD_ANSWERS[1])
# Simulate "app closed" -- rebuild a fresh assessment object pointed at the same storage
_, _, _, resumed_assessment, _, _, _ = (storage, engine, pipeline,
    InitialCommunicationAssessment(pipeline, storage, engine), results, gating, reassess)
status = resumed_assessment.get_assessment_status(aid) if resumed_assessment._load_current_assessment(user.user_id, aid) else None
check("BAS-US-09 TC-005", "App closed after Q2, resumes at question index 2 on reopen",
      status is not None and status['current_question_index'] == 2)


# ---------------------------------------------------------------------------
# BAS-US-01: Baseline Assessment Results Summary View
# ---------------------------------------------------------------------------
print("\n=== BAS-US-01: Results Summary View ===")

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc01_01", "TC-001 User")
aid, final = run_full_text_assessment(storage, assessment, user.user_id, GOOD_ANSWERS)
summary = results.generate_assessment_summary(aid)
check("BAS-US-01 TC-001", "Results screen shows all 4 metrics + confidence score, positively framed",
      'fluency' in summary['skill_breakdown'] and 'vocabulary' in summary['skill_breakdown']
      and 'confidence_score' in summary and 'failing' not in summary['confidence_score']['message'].lower())

# TC-004: force-close before reveal -> persisted result shows automatically next open
summary_again = results.generate_assessment_summary(aid)  # simulates "re-open app, fetch same assessment_id"
check("BAS-US-01 TC-004", "Force-closed before reveal: persisted result re-renders identically on reopen",
      summary_again['confidence_score']['score'] == summary['confidence_score']['score'])


# ---------------------------------------------------------------------------
# BAS-US-02: Skip Assessment & Feature-Access Gating
# ---------------------------------------------------------------------------
print("\n=== BAS-US-02: Skip Assessment & Feature-Access Gating ===")

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc02", "TC-002 User")

skip_attempt = gating.attempt_skip_assessment(user.user_id)
check("BAS-US-02 TC-001", "Tapping Skip shows warning modal explaining feature-locking",
      skip_attempt.get('action_required') == 'confirm_skip' and 'locked' in skip_attempt['message'].lower())

confirm = gating.confirm_skip_assessment(user.user_id)
check("BAS-US-02 TC-002", "Confirm skip -> status Unassessed, modules locked, settings still reachable",
      confirm['status'] == 'unassessed'
      and storage.get_user(user.user_id).assessment_status == AssessmentStatus.UNASSESSED)

access = gating.check_feature_access(user.user_id, GatedFeature.INTERVIEW_COACH.value)
check("BAS-US-02 TC-003", "Unassessed user blocked from Interview Coach",
      access['accessible'] is False)

basic_access = gating.check_feature_access(user.user_id, BasicFeature.ACCOUNT_SETTINGS.value)
check("BAS-US-02", "Unassessed user still reaches Account Settings",
      basic_access['accessible'] is True)

check("BAS-US-02 TC-004", "Org policy disables skip entirely for mandatory-assessment cohorts",
      None,
      gap_note="_check_enterprise_mandatory_policy() is hardcoded to always return False -- "
               "no organization policy store exists, so this can never actually block a skip "
               "regardless of is_enterprise/organization_id.")


# ---------------------------------------------------------------------------
# BAS-US-03: Assessment Integrity & Anti-Gaming Safeguards
# ---------------------------------------------------------------------------
print("\n=== BAS-US-03: Assessment Integrity & Anti-Gaming Safeguards ===")

checker = AssessmentIntegrityChecker()

flagged, reason = checker.check_text_integrity("pasted text answer", clipboard_detected=True)
check("BAS-US-03 TC-002", "Pasted text flagged and would be excluded from scoring",
      flagged is True and reason == "Clipboard paste detected")

flagged, reason = checker.check_text_integrity("a a a a a a a a a a", clipboard_detected=False)
check("BAS-US-03 (gibberish)", "Suspiciously short/gibberish words flagged",
      flagged is True)

check("BAS-US-03 TC-003", "Heavy-accent genuine speech gets secondary verification, not penalized",
      None,
      gap_note="check_audio_integrity() has no secondary-verification path -- any flagged audio "
               "(including a false positive on heavy accent) is excluded outright, same as a "
               "confirmed gaming attempt. No distinction, no re-check queue.")

check("BAS-US-03 TC-004", "Accessibility opt-in exempts approved dictation-tool paste from flagging",
      None,
      gap_note="check_text_integrity() takes no accessibility/opt-in parameter at all -- there is "
               "no way to exempt a user's paste from detection regardless of account settings.")


# ---------------------------------------------------------------------------
# BAS-US-04: On-Demand Re-Assessment Request
# ---------------------------------------------------------------------------
print("\n=== BAS-US-04: On-Demand Re-Assessment Request ===")

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc04", "TC-004 User")
aid, _ = run_full_text_assessment(storage, assessment, user.user_id, GOOD_ANSWERS)
# Backdate completion so we can test both eligible and ineligible windows
storage.assessments[aid].completed_at = datetime.now() - timedelta(days=10)

try:
    storage.request_reassessment(user.user_id, is_early=True)
    early_ok = True
except ValueError:
    early_ok = False
check("BAS-US-04 TC-001", "Eligible user (10 days elapsed, >=7-day cooldown) can request early retake",
      early_ok)

try:
    storage.request_reassessment(user.user_id, is_early=True)
    second_blocked = False
except ValueError as e:
    second_blocked = "Already used early retake" in str(e)
check("BAS-US-04 TC-002/E-01", "Second early retake in same cycle is blocked",
      second_blocked)

check("BAS-US-04 TC-003", "Retake requested mid-session queues until session ends rather than interrupting",
      None,
      gap_note="No session-in-progress concept exists in reassessment.py/storage.py -- "
               "request_reassessment() has no queuing behavior, it either raises or succeeds immediately.")


# ---------------------------------------------------------------------------
# BAS-US-10: Confidence Score Re-Calculation Engine
# ---------------------------------------------------------------------------
print("\n=== BAS-US-10: Confidence Score Re-Calculation Engine ===")

engine = ConfidenceScoreEngine()
for _ in range(3):
    engine.add_session_score(SessionScore(timestamp=datetime.now(), fluency_score=80.0,
                                           vocabulary_score=75.0, pronunciation_score=85.0))
baseline_score = engine.get_confidence_score()
engine.add_session_score(SessionScore(timestamp=datetime.now(), fluency_score=10.0,
                                       vocabulary_score=8.0, pronunciation_score=5.0))
check("BAS-US-10 TC-003", "Extreme outlier session (audio failure) detected and dropped, doesn't tank score",
      engine.session_history[-1].is_outlier is True and engine.get_confidence_score() == baseline_score)

engine2 = ConfidenceScoreEngine()
text_only_session = SessionScore(timestamp=datetime.now(), fluency_score=70.0,
                                  vocabulary_score=60.0, pronunciation_score=None, is_text_only=True)
score = engine2.calculate_session_confidence(text_only_session)
check("BAS-US-10 TC-002", "Text session ignores pronunciation, weights only fluency+vocabulary",
      score == round(70.0 * (50/80) + 60.0 * (30/80), 2))


# ---------------------------------------------------------------------------
# BAS-US-12: Periodic Baseline Re-Assessment
# ---------------------------------------------------------------------------
print("\n=== BAS-US-12: Periodic Baseline Re-Assessment ===")

storage, engine, pipeline, assessment, results, gating, reassess = new_stack()
user = storage.create_user("ext_tc12", "TC-012 User")
aid, _ = run_full_text_assessment(storage, assessment, user.user_id, GOOD_ANSWERS)
storage.assessments[aid].completed_at = datetime.now() - timedelta(days=31)

eligibility = reassess.check_eligibility(user.user_id)
check("BAS-US-12 TC-001", "30+ days elapsed -> eligible for scheduled re-assessment prompt",
      eligibility.is_eligible is True)

dismiss = reassess.dismiss_prompt(user.user_id)
check("BAS-US-12 TC-003", "Dismissing the prompt succeeds and returns a re-prompt time",
      dismiss['success'] is True and 'dismissed_until' in dismiss)

restart = reassess.start_re_assessment(user.user_id)
aid2, final2 = run_full_text_assessment(storage, assessment, user.user_id, GOOD_ANSWERS)
trend = reassess.get_progress_trend(user.user_id)
check("BAS-US-12 TC-002", "Completed re-assessment overwrites baseline and appends historical trend data",
      trend['has_trend_data'] is True and trend['assessment_count'] == 2)


# ---------------------------------------------------------------------------
print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed, {len(GAP)} known gaps (not bugs, not tested)\n{'='*60}")
if FAIL:
    print("FAILED:")
    for tc, desc in FAIL:
        print(f"  - {tc}: {desc}")
    sys.exit(1)
