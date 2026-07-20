"""Prompt library (lib/prompts) — workplace coaching + ported conversation prompts."""

from lib import prompts


def test_all_scenarios_present():
    keys = set(prompts.WORKPLACE_SCENARIOS)
    assert keys == {
        "email_writing", "client_communication", "meeting_communication",
        "presentation_prep", "general_workplace",
    }
    for meta in prompts.WORKPLACE_SCENARIOS.values():
        assert meta["input_mode"] in ("text", "audio")
        assert meta["prompts"]


def test_feedback_prompt_includes_context_and_json_shape():
    p = prompts.build_workplace_feedback_prompt(
        scenario_label="Email Writing",
        prompt="Email your manager about a delay.",
        submission="thx bro, project late",
        input_mode="text",
    )
    assert "Email Writing" in p
    assert "thx bro" in p
    assert "professional_tone" in p
    assert "PROFESSIONAL TONE" in p  # tone graded as headline


def test_feedback_prompt_audio_includes_delivery_metrics():
    p = prompts.build_workplace_feedback_prompt(
        scenario_label="Presentation Preparation",
        prompt="Present Q3 results.",
        submission="today I will cover our numbers",
        input_mode="audio",
        delivery_metrics={"speech_rate": 3.1, "pause_count": 2, "filled_pauses": 1,
                          "duration_seconds": 40.0},
    )
    assert "speech_rate" in p
    assert "transcribed" in p


def test_roleplay_prompt_only_for_roleplay_scenarios():
    assert prompts.build_workplace_roleplay_prompt("client_communication", "angry client").strip()
    assert prompts.build_workplace_roleplay_prompt("meeting_communication", "budget").strip()
    assert prompts.build_workplace_roleplay_prompt("email_writing", "x") == ""


def test_flag_and_highlight_vocabularies_closed():
    assert "slang" in prompts.FLAG_TYPES
    assert "code_switch" in prompts.FLAG_TYPES
    assert set(prompts.HIGHLIGHT_KINDS) == {"expected_vocab", "transition"}


def test_ported_conversation_prompts_still_work():
    sp = prompts.build_system_prompt("travel", level="beginner")
    assert "Travel & Culture" in sp
    assert "BEGINNER" in sp
    assert "job_interview" in prompts.INTERVIEW_STAGE_PROMPTS
    assert prompts.build_topic_validation_prompt("cooking").count("cooking") >= 1
