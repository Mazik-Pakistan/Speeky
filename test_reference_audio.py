from speeky.reference_audio_playback import ReferenceAudioPlayer

player = ReferenceAudioPlayer()

print("\n=== TEST 1: Normal Speed Playback ===")
result = player.get_reference_audio("s1", "The weather is beautiful today.")
print(result)
print("Expect: status = ok, audio_file created, score_impact = 0")

print("\n=== TEST 2: Slow Speed Playback ===")
result = player.get_reference_audio("s1", "The weather is beautiful today.", speed="slow")
print(result)
print("Expect: status = ok, separate slow audio_file created")

print("\n=== TEST 3: Repeated Listen (E-02) - Nudge After 5 Times ===")
for i in range(6):
    result = player.get_reference_audio("s2", "Practice makes perfect.")
print(result)
print("Expect: nudge = 'Ready to give it a try?' on the 6th listen")

print("\n=== TEST 4: Slow Mode Toggle Persists (E-04) ===")
result = player.toggle_slow_speed(True)
print(result)
print("Expect: status = ok, slow_mode = True")

print("\n=== TEST 5: Playback Interrupted (E-03) ===")
result = player.handle_playback_interruption("s1")
print(result)
print("Expect: status = restart_from_beginning")

print("\n=== TEST 6: Pre-cache Upcoming Sentences (E-05) ===")
sentences = [("s3", "Hello there."), ("s4", "How are you?"), ("s5", "Nice to meet you."), ("s6", "Extra one.")]
result = player.precache_upcoming_sentences(sentences)
print(result)
print("Expect: only first 3 sentence IDs cached (s3, s4, s5)")