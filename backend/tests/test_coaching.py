"""Workplace English Coach logic (services/coaching_service) — WEC-US-08..12.

Pure-logic coverage of the exception handling, offline grader, scoring-pipeline routing,
and confidence-first scoring. No DB / no network (LLM forced offline via conftest)."""

import pytest

from lib import llm_client
from lib.session_scorer import AudioFeatures
from services import coaching_service as cs


# ── Rule-based exception handling (precheck) ──────────────────────────────────
def test_email_missing_subject_blocks():  # WEC-US-08 E-03 / TC-05
    blocking, flags = cs.precheck("email_writing", "text",
                                  "Hi, the report is attached and ready for review please.",
                                  subject="", audio=None)
    assert blocking and blocking["flag"] == "empty_subject"
    assert "subject line" in blocking["message"].lower()


def test_email_with_subject_passes_precheck():
    blocking, flags = cs.precheck("email_writing", "text",
                                  "Hi team, the quarterly report is attached for your review.",
                                  subject="Q3 Report", audio=None)
    assert blocking is None


def test_blank_text_blocks():  # WEC-US-09 E-03 / TC-03
    blocking, _ = cs.precheck("email_writing", "text", "too short", subject="Hi", audio=None)
    assert blocking and blocking["flag"] == "blank_submission"


def test_mic_quiet_flag():  # WEC-US-12 E-04
    audio = AudioFeatures(transcript="today I will cover results", duration_seconds=20, avg_db=-60.0)
    blocking, flags = cs.precheck("presentation_prep", "audio",
                                  "today I will cover results", subject=None, audio=audio)
    assert blocking is None
    assert any(f["type"] == "microphone_quiet" for f in flags)


def test_meeting_silence_is_missed_opportunity_not_error():  # WEC-US-11 E-01 / TC-02
    audio = AudioFeatures(transcript="", duration_seconds=60)
    blocking, flags = cs.precheck("meeting_communication", "audio", "", subject=None, audio=audio)
    assert blocking is None
    assert any(f["type"] == "no_interjection" for f in flags)


def test_client_long_monologue_flag():  # WEC-US-10 E-03 / TC-03
    audio = AudioFeatures(transcript="I will explain everything in detail " * 30,
                          duration_seconds=260)
    _, flags = cs.precheck("client_communication", "audio",
                           audio.transcript, subject=None, audio=audio)
    assert any(f["type"] == "long_monologue" for f in flags)


def test_empty_audio_non_meeting_blocks():
    audio = AudioFeatures(transcript="", duration_seconds=30)
    blocking, _ = cs.precheck("presentation_prep", "audio", "", subject=None, audio=audio)
    assert blocking and blocking["flag"] == "blank_submission"


# ── Offline heuristic grader ─────────────────────────────────────────────────
def test_slang_flagged():  # WEC-US-08 TC-02
    fb = cs.offline_feedback("email_writing", "Email client", "thx bro, will do it asap", "text")
    assert any(f["type"] == "slang" for f in fb["flags"])


def test_code_switch_flagged_with_english_equivalent():  # WEC-US-08 E-02 / WEC-US-10 E-04
    fb = cs.offline_feedback("email_writing", "Email client", "Please jaldi reply to this", "text")
    cs_flags = [f for f in fb["flags"] if f["type"] == "code_switch"]
    assert cs_flags and "quickly" in cs_flags[0]["suggestion"]


def test_aggressive_tone_flagged():  # WEC-US-09 E-01 / TC-02
    fb = cs.offline_feedback("email_writing", "Email manager",
                             "You didn't do your job and you always ignore deadlines.", "text")
    assert any(f["type"] == "aggressive_tone" for f in fb["flags"])
    assert fb["professional_tone"] < 70


def test_boilerplate_flagged():  # WEC-US-08/09 E-04
    fb = cs.offline_feedback("email_writing", "Email",
                             "To whom it may concern, please find attached herewith the document.", "text")
    assert any(f["type"] == "boilerplate" for f in fb["flags"])


def test_presentation_missing_intro_and_casual_conclusion():  # WEC-US-12 E-01/E-02
    fb = cs.offline_feedback("presentation_prep", "Present Q3",
                             "Revenue was 2 million and costs were high. So yeah, that's pretty much it.",
                             "audio")
    kinds = {f["type"] for f in fb["flags"]}
    assert "missing_intro" in kinds
    assert "casual_conclusion" in kinds


def test_presentation_transitions_highlighted():  # WEC-US-12 TC-04
    fb = cs.offline_feedback("presentation_prep", "Present Q3",
                             "Today I'd like to cover results. Moving on to the next slide, as you can see revenue grew.",
                             "audio")
    assert any(h["kind"] == "transition" for h in fb["highlights"])


def test_over_promising_flagged_for_client():  # WEC-US-10 E-02
    fb = cs.offline_feedback("client_communication", "Angry client",
                             "I guarantee this will never happen again, whatever it takes.", "audio")
    assert any(f["type"] == "over_promising" for f in fb["flags"])


def test_clean_professional_message_scores_high():  # WEC-US-09 TC-01
    fb = cs.offline_feedback(
        "email_writing", "Email manager",
        "Hi Sarah, I wanted to flag that the project will slip by about a week. "
        "I'll share a revised timeline tomorrow so we can adjust priorities. Thank you for understanding.",
        "text")
    assert fb["flags"] == []
    assert fb["professional_tone"] >= 80
    assert fb["met_objective"] is True


# ── Workplace confidence (confidence-first, grammar-independent) ──────────────
def test_confidence_is_tone_driven_and_penalized_by_flags():
    scored = cs.session_scorer.score_text_session("A reasonably long professional draft " * 5)
    good = {"professional_tone": 90, "clarity": 85, "effectiveness": 85}
    bad = {"professional_tone": 40, "clarity": 60, "effectiveness": 55}
    assert cs.workplace_confidence(good, scored, []) > cs.workplace_confidence(bad, scored, [])
    penalized = cs.workplace_confidence(good, scored, [{"type": "aggressive_tone"}])
    assert penalized < cs.workplace_confidence(good, scored, [])


def test_audio_confidence_uses_pronunciation():
    a = cs.session_scorer.score_audio_session(
        AudioFeatures(transcript="clear steady delivery here", duration_seconds=2,
                      speech_rate=3.0, pause_count=0, filled_pauses=0, pronunciation_score=95))
    b = cs.session_scorer.score_audio_session(
        AudioFeatures(transcript="clear steady delivery here", duration_seconds=2,
                      speech_rate=3.0, pause_count=0, filled_pauses=0, pronunciation_score=20))
    grader = {"professional_tone": 80, "clarity": 80, "effectiveness": 80}
    assert cs.workplace_confidence(grader, a, []) > cs.workplace_confidence(grader, b, [])


# ── Presentation slide-pause tolerance (WEC-US-12 E-03 / TC-05) ───────────────
def test_presentation_long_pause_with_transitions_not_penalized():
    with_transitions = AudioFeatures(
        transcript="On this slide you can see revenue. Moving on to the next slide, costs fell.",
        duration_seconds=30, speech_rate=3.0, pause_count=6, mean_pause_duration=5.0, filled_pauses=0)
    without = AudioFeatures(
        transcript="revenue went up and then costs fell and profit rose overall nicely",
        duration_seconds=30, speech_rate=3.0, pause_count=6, mean_pause_duration=5.0, filled_pauses=0)
    fluent_pres = cs.score_submission("presentation_prep", "audio", with_transitions.transcript, with_transitions)
    penalized = cs.score_submission("meeting_communication", "audio", without.transcript, without)
    assert fluent_pres.fluency_score > penalized.fluency_score


# ── Grading dispatch: offline fallback + LLM path ────────────────────────────
async def test_grade_submission_offline_when_unconfigured():
    fb = await cs.grade_submission("email_writing", "Email", "thx bro just do it", "text")
    assert fb["_source"] == "offline"
    assert any(f["type"] == "slang" for f in fb["flags"])


async def test_grade_submission_uses_llm_and_normalizes(monkeypatch):
    async def fake_json(messages, **kw):
        return {
            "professional_tone": 72, "clarity": 80, "effectiveness": 77, "met_objective": True,
            "flags": [
                {"type": "slang", "phrase": "thx", "explanation": "x", "suggestion": "y"},
                {"type": "totally_made_up", "phrase": "z"},  # must be dropped
            ],
            "highlights": [{"kind": "transition", "phrase": "moving on"},
                           {"kind": "bogus", "phrase": "q"}],  # bogus dropped
            "polished_version": "Polished.", "summary": "ok",
        }
    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_client, "chat_json", fake_json)

    fb = await cs.grade_submission("email_writing", "Email", "thx", "text")
    assert fb["_source"] == "llm"
    assert [f["type"] for f in fb["flags"]] == ["slang"]  # unknown type filtered
    assert [h["kind"] for h in fb["highlights"]] == ["transition"]
    assert fb["professional_tone"] == 72


async def test_grade_submission_falls_back_on_llm_error(monkeypatch):
    async def boom(messages, **kw):
        raise llm_client.LLMError("api down")
    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_client, "chat_json", boom)
    fb = await cs.grade_submission("email_writing", "Email", "You failed to do your job.", "text")
    assert fb["_source"] == "offline"


# ── build_result merge ───────────────────────────────────────────────────────
def test_build_result_headline_and_flag_merge():
    scored = cs.session_scorer.score_text_session("Hi team, please review the attached report today.")
    grader = cs.offline_feedback("email_writing", "Email", "thx bro", "text")
    rule_flags = [{"type": "microphone_quiet", "message": "quiet"}]
    result = cs.build_result("email_writing", "text", grader, scored, rule_flags)
    assert result["headline_metric"] == "professional_tone"
    assert result["scores"]["confidence"] is not None
    # rule flag + grader flags both present
    types = {f["type"] for f in result["flags"]}
    assert "microphone_quiet" in types and "slang" in types


# ── Roleplay reply (WEC-US-10 / WEC-US-11) offline behaviour ─────────────────
async def test_roleplay_switches_back_to_english():  # WEC-US-10 E-04
    reply = await cs._roleplay_reply("client_communication", "angry client",
                                     [{"role": "user", "content": "acha theek hai bhai"}],
                                     end_early=False, switched_language=True)
    assert "English" in reply


async def test_roleplay_end_early_offline():  # WEC-US-10 E-01
    reply = await cs._roleplay_reply("client_communication", "angry client",
                                     [{"role": "user", "content": "you failed"}],
                                     end_early=True, switched_language=False)
    assert reply
