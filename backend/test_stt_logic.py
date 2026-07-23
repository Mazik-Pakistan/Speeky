import asyncio
import json
from lib.pronunciation_coach import (
    word_timings_to_attempts,
    PronunciationPipeline,
    TroubleWordsBank,
    AccessibilityProfile,
    AccessibilityProfileStore
)
from lib.pronunciation_coach.pronunciation_pipeline import ColorTier

async def main():
    print("=== Testing US-74, 75, 76, 79 Integration (Without Frontend) ===\n")

    # 1. Simulate REAL STT Output from Faster-Whisper
    # (Imagine the user stuttered on "world" and said it twice, and missed "today")
    stt_output = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 0.9},
        {"word": "world", "start": 1.0, "end": 1.5},  # Stutter/Repetition
        # "today" is completely omitted
    ]
    target_sentence = "Hello world today"
    
    print(f"Target Sentence: '{target_sentence}'")
    print(f"Simulated STT Word Timings from Whisper:\n{json.dumps(stt_output, indent=2)}\n")

    # 2. Test ASR Adapter (Converts STT to WordAttempts)
    attempts = word_timings_to_attempts(stt_output, target_sentence)
    
    # 3. Test US-74 (Word-level highlighting) & US-75 (Accessibility)
    pipeline = PronunciationPipeline()
    
    print("--- SCORING WITHOUT ACCESSIBILITY PROFILE ---")
    res_normal = pipeline.score_sentence(target_sentence, attempts)
    print(f"Fluency Score: {res_normal.fluency_score}")
    for w in res_normal.words:
        print(f"Word: '{w.target_word}' | Color: {w.tier.name} | Strikethrough: {w.strikethrough} | Note: {w.note}")
    
    print("\n--- SCORING WITH ACCESSIBILITY PROFILE (Opted-in for disfluency) ---")
    # Simulate a user who has opted in for stuttering/repetition exemptions (US-75)
    exempt_indices = {1}  # Exempt the word "world"
    res_access = pipeline.score_sentence(target_sentence, attempts, accessibility_exempt_indices=exempt_indices)
    print(f"Fluency Score: {res_access.fluency_score} (Notice it's higher!)")
    for w in res_access.words:
        print(f"Word: '{w.target_word}' | Color: {w.tier.name} | Note: {w.note}")

    print("\n--- US-79 (Trouble Words) ---")
    # Simulate saving failed words to the trouble bank
    bank = TroubleWordsBank()
    await bank.process_session("dummy_user_1", res_normal)
    profile = await bank.get_user_profile("dummy_user_1")
    print(f"Trouble Words Tracked for User: {[w.word for w in profile.active_words]}")
    
if __name__ == "__main__":
    asyncio.run(main())
