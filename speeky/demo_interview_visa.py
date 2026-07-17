"""
demo_interview_visa.py — Interactive test for VisaInterviewSession.

IMPORTANT: ask_llm_demo below is still NOT the real LLM. It's a slightly
smarter stub than the fixed-string ones used earlier — it does basic
real checks on YOUR actual typed input (keyword/number matching) so
varying what you type actually changes the output. This is still fake
judgment, just reactive fake judgment instead of static fake judgment.
The real ConversationEngine, once wired in, will replace this entirely
with genuine understanding.

Run from the parent of the speeky package:
    python -m speeky.demo_interview_visa
"""

import re

from .interview_visa import VisaInterviewSession

RECOGNIZED_VISA_KEYWORDS = ["f1", "b1", "b2", "h1b", "student", "tourist", "work"]
VAGUE_PHRASES = ["not sure", "maybe", "might", "i don't know", "perhaps", "i'm not certain"]


def ask_llm_demo(prompt: str, context_type: str) -> str:
    if "recognized visa category" in prompt:
        visa_type = prompt.split("Is '")[1].split("'")[0].lower()
        is_known = any(kw in visa_type for kw in RECOGNIZED_VISA_KEYWORDS)
        return "YES" if is_known else "NO"

    if "contradictions" in prompt:
        # Extract "N week(s)" and "N month(s)" mentions from the stated facts list
        # embedded in the prompt, and flag if a short trip co-occurs with long-term funding.
        weeks = re.findall(r"(\d+)\s*week", prompt)
        months = re.findall(r"(\d+)\s*month", prompt)
        if weeks and months and int(months[0]) >= 3:
            return f"CONTRADICTION: You mentioned {weeks[0]} week(s) earlier — why {months[0]} months of funding?"
        return "NONE"

    if "vague/ambiguous" in prompt:
        answer = prompt.split('Answer: "')[1].split('"')[0].lower()
        return "YES" if any(phrase in answer for phrase in VAGUE_PHRASES) else "NO"

    return "Can you tell me more about your travel plans?"


def main():
    print("US-51 Demo — Visa Interview Simulation")
    print("(Stub reacts to real keywords/numbers in your input — still not the real LLM.)\n")

    visa_type = input("Visa type (e.g. 'F1 Student', 'B2 Tourist', or something made up): ").strip()
    s = VisaInterviewSession(ask_llm=ask_llm_demo)
    result = s.start_session(visa_type)
    print("\n>>>", result, "\n")

    total_elapsed = 0.0
    total_words = 0

    print("Type 'quit' to end the session and see your brevity score.\n")
    while True:
        answer = input("Your answer: ").strip()
        if answer.lower() == "quit":
            break

        elapsed_str = input("  How many seconds did that answer take? ").strip()
        silence_str = input("  How many seconds of silence before answering? ").strip()
        elapsed_seconds = float(elapsed_str) if elapsed_str else 0.0
        silence_seconds = float(silence_str) if silence_str else 0.0

        total_elapsed += elapsed_seconds
        total_words += len(answer.split())

        result = s.submit_answer(
            answer, elapsed_seconds=elapsed_seconds, silence_duration_seconds=silence_seconds
        )
        print(">>>", result, "\n")

    end_result = s.end_session(total_elapsed_seconds=total_elapsed, total_word_count=total_words)
    print("\n=== SESSION END ===")
    print(f"Total time: {total_elapsed}s, total words: {total_words}")
    print(end_result)


if __name__ == "__main__":
    main()
