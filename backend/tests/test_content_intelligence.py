"""Sprint 3 content intelligence — US-192, US-193, US-195, US-196, US-198.

Covers the pure decision logic of each service: the scoring maths, the acceptance
criteria that must hold structurally, and every documented exception case. The
DB/HTTP layers are exercised separately against the running stack.
"""

from datetime import datetime, timedelta, timezone

import pytest

from services import content_drift_service as drift
from services import deployment_confidence_service as deploy
from services import prompt_explainability_service as explain
from services import template_performance_service as perf
from services import vocab_coverage_service as vocab


# ── US-192: Vocabulary Coverage Score (CM-US-08) ─────────────────────────────
BASE_SCENARIO = {
    "title": "Hotel check-in",
    "category": "Travel",
    "intent": "Practise checking into a hotel when the booking is missing",
    "persona": "a busy receptionist",
    "difficulty": "intermediate",
}


@pytest.mark.parametrize(
    "words,expect_pair",
    [
        (["negotiate", "negotiating"], True),
        (["negotiate", "negotiation"], True),
        (["refund", "refunds"], True),
        (["reimburse", "reimbursement"], True),
        (["deliver", "delivery"], True),
        (["ship", "shipping"], True),
        # Distinct words that a naive similarity ratio flags as duplicates.
        (["receipt", "recipe"], False),
        (["invoice", "invite"], False),
        (["bill", "billion"], False),
        (["car", "carpet"], False),
        (["refund", "warranty"], False),
        # Enumerated items, not inflections: stripping digits from the stem made
        # every one of these collapse into a single "duplicate" cluster.
        (["COVID-19", "COVID-20"], False),
        (["Type 1", "Type 2"], False),
        (["level 1", "level 10"], False),
        (["Q1 target", "Q2 target"], False),
    ],
)
def test_redundancy_detects_inflections_without_false_positives(words, expect_pair):
    assert bool(vocab.find_redundant_pairs(words)) is expect_pair


def test_distinct_words_never_mass_collapse():
    """Regression: 200 distinct words once produced all 19,900 possible pairs
    because `_stem` discarded digits, so every "wordN" stemmed to "word"."""
    assert vocab.find_redundant_pairs([f"word{i}" for i in range(200)]) == []


def test_empty_vocabulary_scores_zero_with_gap_flag():
    result = vocab.offline_score_coverage({**BASE_SCENARIO, "target_vocab": []})
    assert result["coverage_score"] == 0
    assert vocab.FLAG_VOCABULARY_GAPS in result["flags"]


def test_recommendations_are_always_provided():
    """CM-US-08 acceptance: "Coverage recommendations provided automatically."."""
    strong = {**BASE_SCENARIO, "target_vocab": [
        "reservation", "confirmation", "availability", "upgrade",
        "complimentary", "itinerary", "concierge", "amenities",
    ]}
    assert vocab.offline_score_coverage(strong)["recommendations"]
    assert vocab._ensure_recommendations([], 90)
    assert vocab._ensure_recommendations([], 10)


def test_repetition_and_difficulty_flags():
    repeated = vocab.offline_score_coverage({**BASE_SCENARIO, "target_vocab": [
        "refund", "refunds", "reservation", "confirmation", "availability"]})
    assert vocab.FLAG_EXCESSIVE_REPETITION in repeated["flags"]

    mismatched = vocab.offline_score_coverage({
        **BASE_SCENARIO, "difficulty": "advanced",
        "target_vocab": ["buy", "get", "pay", "ask", "give", "take"]})
    assert vocab.FLAG_INCORRECT_DIFFICULTY in mismatched["flags"]


# ── US-193: Template Performance Dashboard (CM-US-09) ────────────────────────
class FakeSession:
    def __init__(self, status, conf=None, target=None, used=None, rating=None, age_hours=1):
        self.status = status
        self.confidenceScore = conf
        self.targetVocab = target or []
        self.vocabUsed = used or []
        self.satisfactionRating = rating
        self.createdAt = datetime.now(timezone.utc) - timedelta(hours=age_hours)


class FakeScenario:
    def __init__(self, age_hours=1000, status="ACTIVE"):
        self.createdAt = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        self.status = status


def test_no_sessions_reports_no_analytics_not_zero():
    """A metric with no data must be None — 0% completion and "nobody tried it"
    are different facts and must not render identically."""
    metrics = perf.compute_metrics([], FakeScenario())
    assert metrics["usage_count"] == 0
    assert metrics["completion_rate"] is None
    assert metrics["no_analytics"] is True


def test_newly_published_is_distinguished_from_underperforming():
    assert perf.compute_metrics([], FakeScenario(age_hours=2))["newly_published"] is True
    assert perf.compute_metrics([], FakeScenario(age_hours=500))["newly_published"] is False


def test_metric_aggregation():
    sessions = [
        FakeSession("completed", 80, ["a", "b"], ["a"], 5),
        FakeSession("completed", 60, ["a", "b"], ["a", "b"], 3),
        FakeSession("ended_early", None, ["a", "b"], []),
        FakeSession("in_progress", None, ["a", "b"], [], age_hours=48),  # stale -> abandoned
        FakeSession("in_progress", None, ["a", "b"], [], age_hours=1),   # live -> not abandoned
    ]
    m = perf.compute_metrics(sessions, FakeScenario())
    assert m["usage_count"] == 5
    assert m["completion_rate"] == 40.0
    assert m["average_learner_score"] == 70.0       # unscored rows excluded
    assert m["vocabulary_success_rate"] == 30.0
    assert m["session_abandonment"] == 40.0          # ended_early + stale only
    assert m["learner_satisfaction"] == 4.0
    assert m["satisfaction_responses"] == 2


def test_unrated_sessions_do_not_read_as_zero_satisfaction():
    m = perf.compute_metrics([FakeSession("completed", 70, ["a"], ["a"])], FakeScenario())
    assert m["learner_satisfaction"] is None
    assert m["satisfaction_responses"] == 0


def test_confidence_improvement_needs_enough_history():
    few = [FakeSession("completed", 70, age_hours=i) for i in range(3)]
    assert perf.compute_metrics(few, FakeScenario())["confidence_improvement"] is None

    rising = [FakeSession("completed", c, age_hours=100 - i * 10)
              for i, c in enumerate([40, 45, 50, 60, 65, 70, 80, 85, 90])]
    assert perf.compute_metrics(rising, FakeScenario())["confidence_improvement"] == 40.0


# ── US-195: Prompt Explainability Report (CM-US-11) ──────────────────────────
def test_every_deduction_is_explained_even_when_the_model_skips_them():
    """CM-US-11 acceptance: "Every deduction in scoring must include an
    explanation." The model is asked but not trusted — the server fills gaps."""
    breakdown = {
        "prompt_completeness": 40, "persona_consistency": 100,
        "scenario_clarity": 65, "vocabulary_relevance": 80,
        "learning_objective_alignment": 55,
    }
    only_one_explained = [
        {"dimension": "prompt_completeness", "score": 40, "explanation": "Too thin."}
    ]
    deductions = explain._reconcile_deductions(only_one_explained, breakdown)

    assert len(deductions) == 4                                   # the 100 is excluded
    assert all(d["explanation"].strip() for d in deductions)
    assert {d["dimension"] for d in deductions} == {
        "prompt_completeness", "scenario_clarity",
        "vocabulary_relevance", "learning_objective_alignment",
    }
    assert [d["source"] for d in deductions].count("synthesised") == 3


def test_deductions_are_ordered_by_severity():
    breakdown = {"a": 90, "b": 20, "c": 60}
    assert [d["dimension"] for d in explain._reconcile_deductions([], breakdown)] == ["b", "c", "a"]


def test_malformed_model_deductions_are_ignored_not_crashed():
    breakdown = {"scenario_clarity": 50}
    junk = ["a string", {"dimension": "", "explanation": "x"}, {"dimension": "y"}, None]
    deductions = explain._reconcile_deductions(junk, breakdown)
    assert len(deductions) == 1 and deductions[0]["source"] == "synthesised"


def test_offline_explanation_marks_itself_low_confidence():
    report = explain.offline_explain(
        {"system_prompt": "Be a receptionist.", "target_vocab": ["a"]}, 60, {"scenario_clarity": 60}, 55)
    assert report["low_confidence"] is True
    assert report["_source"] == "offline"


# ── US-196: Content Drift Detection (CM-US-12) ───────────────────────────────
HEALTHY_BASELINE = {
    "completion_rate": 80, "vocabulary_success_rate": 70, "average_learner_score": 75,
    "confidence_improvement": 5, "learner_satisfaction": 4.0, "session_abandonment": 10,
}


def test_seasonal_variation_is_not_drift():
    """Deltas inside the tolerance band are normal fluctuation."""
    recent = {**HEALTHY_BASELINE, "completion_rate": 75}
    assert drift.compare_windows(HEALTHY_BASELINE, recent)["severity"] is None


def test_single_modest_dip_is_an_anomaly_not_an_alert():
    recent = {**HEALTHY_BASELINE, "completion_rate": 68}
    assert drift.compare_windows(HEALTHY_BASELINE, recent)["severity"] == "INFO"


def test_multiple_degraded_signals_escalate():
    two = drift.compare_windows(HEALTHY_BASELINE, {
        **HEALTHY_BASELINE, "completion_rate": 65, "vocabulary_success_rate": 55})
    assert two["severity"] == "WARNING"

    three = drift.compare_windows(HEALTHY_BASELINE, {
        **HEALTHY_BASELINE, "completion_rate": 60,
        "vocabulary_success_rate": 50, "average_learner_score": 55})
    assert three["severity"] == "CRITICAL"


def test_one_severe_signal_is_critical():
    assert drift.compare_windows(
        HEALTHY_BASELINE, {**HEALTHY_BASELINE, "completion_rate": 40})["severity"] == "CRITICAL"


def test_rising_abandonment_is_degradation():
    result = drift.compare_windows(HEALTHY_BASELINE, {**HEALTHY_BASELINE, "session_abandonment": 45})
    assert "session_abandonment" in result["degraded"]


def test_improvement_is_never_flagged_as_drift():
    better = {**HEALTHY_BASELINE, "completion_rate": 95, "session_abandonment": 2}
    assert drift.compare_windows(HEALTHY_BASELINE, better)["severity"] is None


def test_missing_data_produces_no_false_alert():
    empty = dict.fromkeys(HEALTHY_BASELINE)
    assert drift.compare_windows(HEALTHY_BASELINE, empty)["severity"] is None


def test_platform_wide_degradation_is_suppressed():
    """CM-US-12 exception: "AI model update impact" — when everything degrades at
    once the cause is the platform, not any one template."""
    analyses = [
        {"status": "analysed", "degraded": ["completion_rate"]},
        {"status": "analysed", "degraded": ["completion_rate"]},
        {"status": "analysed", "degraded": ["completion_rate"]},
        {"status": "analysed", "degraded": []},
    ]
    assert "completion_rate" in drift.suppress_platform_wide(analyses)


def test_one_template_degrading_alone_is_not_suppressed():
    analyses = [
        {"status": "analysed", "degraded": ["completion_rate"]},
        {"status": "analysed", "degraded": []},
        {"status": "analysed", "degraded": []},
        {"status": "analysed", "degraded": []},
    ]
    assert drift.suppress_platform_wide(analyses) == []


# ── US-198: Deployment Confidence Monitoring (CM-US-14) ──────────────────────
class FakeDeployment:
    def __init__(self, score, outcome="DEPLOYED", version=1, age_days=0):
        self.confidenceScore = score
        self.outcome = outcome
        self.version = version
        self.createdAt = datetime.now(timezone.utc) - timedelta(days=age_days)


HEALTHY_BREAKDOWN_INPUT = ({"persona_consistency": 85, "learning_objective_alignment": 80}, 80, 75)


def _healthy():
    quality, confidence, coverage = HEALTHY_BREAKDOWN_INPUT
    breakdown = deploy.compute_breakdown(quality, confidence, coverage, 4, 4, [])
    return breakdown, deploy.score_from_breakdown(breakdown)


def test_healthy_template_clears_deployment():
    breakdown, score = _healthy()
    exceptions = deploy.build_exceptions(breakdown, score, 4, 4, [])
    assert score >= deploy.LOW_CONFIDENCE_THRESHOLD
    assert exceptions["blocking"] == []


def test_e02_sandbox_failure_blocks_deployment():
    breakdown, score = _healthy()
    assert [e["code"] for e in deploy.build_exceptions(breakdown, score, 0, 0, [])["blocking"]] == ["E-02"]
    assert [e["code"] for e in deploy.build_exceptions(breakdown, score, 3, 0, [])["blocking"]] == ["E-02"]


def test_e01_low_confidence_warns_but_does_not_block():
    breakdown = deploy.compute_breakdown({"persona_consistency": 30}, 35, 30, 4, 1, [])
    score = deploy.score_from_breakdown(breakdown)
    result = deploy.build_exceptions(breakdown, score, 4, 1, [])
    assert score < deploy.LOW_CONFIDENCE_THRESHOLD
    assert "E-01" in [e["code"] for e in result["warnings"]]
    assert result["blocking"] == []


def test_e03_prompt_regression_only_past_the_threshold():
    breakdown, score = _healthy()
    just_under = deploy.build_exceptions(breakdown, score, 4, 4, [FakeDeployment(score + 14, version=2)])
    at_threshold = deploy.build_exceptions(breakdown, score, 4, 4, [FakeDeployment(score + 15, version=2)])
    assert "E-03" not in [e["code"] for e in just_under["warnings"]]
    assert "E-03" in [e["code"] for e in at_threshold["warnings"]]


def test_e03_compares_against_the_latest_deployment():
    breakdown, score = _healthy()
    history = [FakeDeployment(60, version=1, age_days=10), FakeDeployment(score + 40, version=3, age_days=1)]
    warning = next(e for e in deploy.build_exceptions(breakdown, score, 4, 4, history)["warnings"]
                   if e["code"] == "E-03")
    assert "version 3" in warning["resolution"]


def test_e05_and_e06_exceptions():
    breakdown, score = _healthy()
    assert "E-05" in [e["code"] for e in
                      deploy.build_exceptions(breakdown, score, 4, 4, [], model_changed=True)["warnings"]]

    unstable = deploy.compute_breakdown({"persona_consistency": 30}, 80, 75, 4, 4, [])
    unstable_score = deploy.score_from_breakdown(unstable)
    assert "E-06" in [e["code"] for e in
                      deploy.build_exceptions(unstable, unstable_score, 4, 4, [])["warnings"]]


def test_deployment_history_penalises_failed_attempts():
    clean = deploy.compute_breakdown({}, 80, 75, 4, 4, [FakeDeployment(90)])
    failed = deploy.compute_breakdown({}, 80, 75, 4, 4, [
        FakeDeployment(90), FakeDeployment(90, "BLOCKED"), FakeDeployment(90, "ROLLED_BACK")])
    assert failed["deployment_history"] < clean["deployment_history"]


def test_legacy_templates_are_not_reported_as_never_tested():
    """Rows published before the sandbox counters existed have runs=0 but a true
    `sandboxTested` flag; reading the raw counters would block every live template."""
    class Row:
        def __init__(self, runs, passes, tested):
            self.sandboxRuns, self.sandboxPasses, self.sandboxTested = runs, passes, tested

    assert deploy._effective_sandbox_counts(Row(0, 0, True)) == (1, 1)
    assert deploy._effective_sandbox_counts(Row(0, 0, False)) == (0, 0)
    assert deploy._effective_sandbox_counts(Row(5, 3, True)) == (5, 3)


def test_scores_stay_within_bounds():
    for quality, confidence, coverage, runs, passes in [
        ({}, None, None, 0, 0),
        ({"persona_consistency": 999}, 999, 999, 10, 10),
        ({"persona_consistency": -50}, -10, -10, 3, 0),
    ]:
        breakdown = deploy.compute_breakdown(quality, confidence, coverage, runs, passes, [])
        score = deploy.score_from_breakdown(breakdown)
        assert 0 <= score <= 100
        assert all(0 <= v <= 100 for v in breakdown.values())
