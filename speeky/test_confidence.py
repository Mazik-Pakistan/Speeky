"""
demo_confidence.py — Interactive US-21 (Confidence vs. Grammar) demo.

WHAT IS REAL vs SIMULATED IN THIS DEMO
---------------------------------------
- grammar_result  -> REAL. Your typed sentence is actually run through
  GrammarCorrector.correct_text() (grammar.py). error_density comes from
  real correction, not a mock.
- fluency_details -> SIMULATED. Confidence scoring needs audio signals
  (speech_rate, pause_count, filled_pauses) that can only come from a
  real recording + FluencyAnalyzer. Since this demo only takes typed
  text, you pick a delivery preset below and we use representative
  fixed numbers for it. This is clearly labelled at runtime.
- error tag for repeat-offender tracking -> HEURISTIC, not real NLP.
  We do a crude keyword diff between your original sentence and the
  corrected sentence to guess a tag (e.g. "past_tense"). Real tagging
  does not exist yet in grammar.py (see confidence.py's TODO notes).
- Session history -> persisted to a local JSON file (session_history.json)
  next to this script, purely so repeat-offender detection has something
  to accumulate across multiple runs. This is a demo stand-in for the
  "no DB/session layer exists yet" gap noted in confidence.py.

Run from D:\\Speeky (the parent of the speeky package):
    python -m speeky.demo_confidence
or, if you place this file directly inside the speeky package folder,
run it the same way as a module so relative imports keep working.
"""

import json
import os
import sys

from speeky.grammar import GrammarCorrector
from speeky.confidence import ConfidenceGrammarAnalyzer

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_history.json")

# SIMULATED fluency presets — representative numbers standing in for
# what FluencyAnalyzer would compute from real audio.
FLUENCY_PRESETS = {
    "1": {
        "label": "Confident & fluent (few pauses, no fillers)",
        "data": {"speech_rate": 3.0, "pause_count": 1, "filled_pauses": 0},
    },
    "2": {
        "label": "Some hesitation (a few pauses/fillers)",
        "data": {"speech_rate": 2.2, "pause_count": 3, "filled_pauses": 2},
    },
    "3": {
        "label": "Lots of pauses & filler words (nervous delivery)",
        "data": {"speech_rate": 1.4, "pause_count": 7, "filled_pauses": 5},
    },
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)


def guess_error_tag(original: str, corrected: str) -> str:
    """
    HEURISTIC ONLY — not real grammar tagging. Crude keyword check to
    make the repeat-offender demo runnable without real tag support in
    grammar.py. Do not treat this as production logic.
    """
    if original.strip() == corrected.strip():
        return None

    past_tense_markers = {"was", "were", "went", "had", "did", "ate", "saw", "took"}
    corrected_words = set(corrected.lower().split())
    original_words = set(original.lower().split())

    if corrected_words & past_tense_markers and not (original_words & past_tense_markers):
        return "past_tense"

    return "other"


def print_organized_report(sentence, fluency_label, grammar_result, result):
    print("\n" + "=" * 60)
    print("US-21 CONFIDENCE VS. GRAMMAR REPORT")
    print("=" * 60)

    print(f"\nSentence (yours, real):      {sentence}")
    print(f"Corrected (real):             {grammar_result.get('corrected')}")
    print(f"Fluency preset (SIMULATED):   {fluency_label}")

    print("\n--- Scores ---")
    print(f"Confidence Score (PRIMARY):   {result['confidence_score']} / 100")
    print(f"Grammar Score (secondary):    {result['grammar_score']} / 100")
    print(f"Grammar Tier:                 {result['grammar_tier']}")
    print(f"Needs Clarification:          {result['needs_clarification']}")

    print("\n--- Feedback ---")
    print(f"{result['feedback_hint']}")

    if result["repeat_offender_tip"]:
        print(f"\n[Repeat Offender Tip] {result['repeat_offender_tip']}")
    else:
        print("\n[Repeat Offender Tip] None yet")

    print("\n" + "=" * 60 + "\n")


def main():
    print("US-21 Demo — type a sentence to analyze.")
    print("(Grammar scoring is real. Fluency/confidence uses a simulated preset")
    print(" since this demo has no real audio input.)\n")

    sentence = input("Enter your sentence: ").strip()
    if not sentence:
        print("No sentence entered, exiting.")
        sys.exit(0)

    print("\nChoose a SIMULATED delivery style (stand-in for real audio):")
    for key, preset in FLUENCY_PRESETS.items():
        print(f"  {key}. {preset['label']}")
    choice = input("Enter 1, 2, or 3: ").strip()
    preset = FLUENCY_PRESETS.get(choice, FLUENCY_PRESETS["1"])

    high_stakes_input = input("\nIs this a high-stakes/professional context? (y/n): ").strip().lower()
    is_high_stakes = high_stakes_input == "y"

    print("\nRunning real grammar correction...")
    corrector = GrammarCorrector(use_llm=False)
    grammar_result = corrector.correct_text(sentence, use_llm=False)

    tag = guess_error_tag(sentence, grammar_result.get("corrected", sentence))
    history = load_history()

    analyzer = ConfidenceGrammarAnalyzer()
    result = analyzer.analyze(
        fluency_details=preset["data"],
        grammar_result=grammar_result,
        is_high_stakes_context=is_high_stakes,
        error_history=history,
        current_error_tags=[tag] if tag else None,
    )

    save_history(result["error_history"])

    print_organized_report(sentence, preset["label"], grammar_result, result)


if __name__ == "__main__":
    main()