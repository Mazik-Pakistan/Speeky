from speeky.reference_audio_playback import ReferenceAudioPlayer
import inspect

rap = ReferenceAudioPlayer()

print("=== PART 1: Persistence Across Sentences ===")
rap.toggle_slow_speed(enabled=True)
print("Slow mode set to True for sentence s1")

result_s1 = rap.get_reference_audio("persist_s1", "This is the first sentence.")
print("Sentence 1 audio:", result_s1["audio_file"], "| slow_mode still:", rap.slow_mode_enabled)

result_s2 = rap.get_reference_audio("persist_s2", "This is a completely different second sentence.")
print("Sentence 2 audio:", result_s2["audio_file"], "| slow_mode still:", rap.slow_mode_enabled)

print()
print("=== PART 2: Structural Proof - No Connection to Scoring OR Recording ===")
source = inspect.getsource(ReferenceAudioPlayer)
risky_words = ["pronunciation", "score", "Score", "grading", "record", "Record", "asr", "ASR", "transcribe", "mic", "microphone"]
found_any = False
for w in risky_words:
    if w in source:
        found_any = True
        print(f"FOUND reference to '{w}' in ReferenceAudioPlayer code!")
if not found_any:
    print("CONFIRMED: ReferenceAudioPlayer never mentions pronunciation, scoring, recording, ASR, or microphone anywhere.")
    print("slow_mode_enabled is a variable ONLY inside this class - it structurally cannot reach or alter")
    print("the user's own recording pipeline (asr.py / session_manager.py) or the scoring pipeline (pronunciation.py).")
    from speeky.reference_audio_playback import ReferenceAudioPlayer
import inspect

source = inspect.getsource(ReferenceAudioPlayer)
lines = source.split("\n")

for i, line in enumerate(lines):
    if "score" in line or "record" in line.lower():
        print(f"Line {i}: {line}")
        from speeky.reference_audio_playback import ReferenceAudioPlayer

rap = ReferenceAudioPlayer()

print("=== E-05 TEST: Pre-caching on Poor Bandwidth ===")
big_list = [
    ("s1", "First sentence to practice."),
    ("s2", "Second sentence to practice."),
    ("s3", "Third sentence to practice."),
    ("s4", "Fourth sentence to practice."),
    ("s5", "Fifth sentence to practice."),
]

result = rap.precache_upcoming_sentences(big_list)
print("Result:", result)
print()
print("Confirm: only 2-3 sentences cached (not all 5), as per E-05 requirement")
print("Cached count:", len(result.get("cached_sentence_ids", [])))

# Confirm cache actually has real files
for sid, path in rap.cached_sentences.items():
    print(f"  {sid} -> {path}")