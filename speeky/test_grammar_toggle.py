"""
demo_grammar_toggle.py — Interactive US-27 (Inline Grammar Correction Toggle) demo.

Nothing here is hardcoded — every sentence, toggle state, and mode comes
from what you type at the prompts below. Grammar correction is REAL
(runs through the actual GrammarCorrector in grammar.py).

Run from the parent of the speeky package:
    python -m speeky.demo_grammar_toggle
"""

from .grammar import GrammarCorrector
from .grammar_toggle import InlineCorrectionChipService


def ask_yes_no(prompt: str) -> bool:
    answer = input(prompt).strip().lower()
    return answer in ("y", "yes")


def main():
    print("US-27 Demo — Inline Grammar Correction Toggle")
    print("Everything below is live: your sentence, your toggle choice, your mode.\n")

    sentence = input("Enter a sentence to send: ").strip()
    if not sentence:
        print("No sentence entered, exiting.")
        return

    show_corrections_enabled = ask_yes_no(
        "Is 'Show corrections during chat' enabled for this session? (y/n): "
    )
    is_voice_mode = ask_yes_no("Are you in voice mode? (y/n): ")

    print("\nRunning real grammar correction...")
    corrector = GrammarCorrector(use_llm=False)
    service = InlineCorrectionChipService(grammar_corrector=corrector)

    result = service.get_correction_chip(
        original_text=sentence,
        show_corrections_enabled=show_corrections_enabled,
        is_voice_mode=is_voice_mode,
        use_llm=False,
    )

    print("\n" + "=" * 60)
    print("US-27 RESULT")
    print("=" * 60)
    print(f"Original:            {sentence}")
    print(f"Corrected:           {result['grammar_result'].get('corrected')}")
    print(f"Toggle enabled:      {show_corrections_enabled}")
    print(f"Voice mode:          {is_voice_mode}")
    print(f"Chip shown inline:   {result['chip']}")
    print(f"Suppressed reason:   {result['suppressed_reason']}")
    print("(Full grammar_result is always kept for the end-of-session summary,")
    print(" regardless of chip suppression.)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()