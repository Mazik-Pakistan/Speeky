"""Text vs audio scoring pipeline (lib/session_scorer)."""

from lib import session_scorer as ss
from lib.session_scorer import AudioFeatures


def test_text_session_has_no_pronunciation():
    scored = ss.score_text_session(
        "I wanted to let you know the project will be delayed by about a week. "
        "I will share a revised timeline tomorrow so we can plan accordingly."
    )
    assert scored.is_text_only is True
    assert scored.pronunciation_score is None
    assert 0 < scored.fluency_score <= 100
    assert 0 < scored.vocabulary_score <= 100
    assert scored.delivery["pipeline"] == "text"


def test_empty_text_scores_zero():
    scored = ss.score_text_session("")
    assert scored.fluency_score == 0.0
    assert scored.vocabulary_score == 0.0


def test_audio_session_has_pronunciation_and_is_not_text_only():
    feats = AudioFeatures(
        transcript="Good morning everyone, today I would like to walk you through our results.",
        duration_seconds=4.0,
        speech_rate=3.0,
        pause_count=1,
        filled_pauses=0,
    )
    scored = ss.score_audio_session(feats)
    assert scored.is_text_only is False
    assert scored.pronunciation_score is not None
    assert scored.delivery["pipeline"] == "audio"
    # ideal pace + no fillers + one pause ⇒ strong fluency
    assert scored.fluency_score >= 70


def test_audio_derives_timing_from_word_timings():
    # 4 words over 2s ⇒ 2 words/sec; a >0.2s gap between word 2 and 3 ⇒ 1 pause
    feats = AudioFeatures(
        transcript="one two three four",
        word_timings=[
            {"word": "one", "start": 0.0, "end": 0.4},
            {"word": "two", "start": 0.4, "end": 0.8},
            {"word": "three", "start": 1.5, "end": 1.8},
            {"word": "four", "start": 1.8, "end": 2.0},
        ],
    )
    scored = ss.score_audio_session(feats)
    assert scored.delivery["pause_count"] == 1
    assert 1.5 <= scored.delivery["speech_rate"] <= 2.5


def test_filler_words_lower_fluency():
    clean = AudioFeatures(transcript="I propose we increase the budget next quarter.",
                          duration_seconds=3.0, speech_rate=3.0, pause_count=0, filled_pauses=0)
    disfluent = AudioFeatures(transcript="um so like uh I think um maybe like you know",
                              duration_seconds=6.0, speech_rate=1.5, pause_count=8, filled_pauses=6)
    assert ss.score_audio_session(clean).fluency_score > ss.score_audio_session(disfluent).fluency_score


def test_supplied_pronunciation_is_used():
    feats = AudioFeatures(transcript="hello there", duration_seconds=1.0,
                          speech_rate=2.0, pronunciation_score=42.0)
    scored = ss.score_audio_session(feats)
    assert scored.pronunciation_score == 42.0
    assert scored.delivery["pronunciation_estimated"] is False


def test_count_filled_pauses():
    assert ss.count_filled_pauses("um so uh I mean like yeah") >= 3
    assert ss.count_filled_pauses("A clear professional sentence.") == 0
