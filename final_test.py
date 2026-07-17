from speeky.session_manager import SessionManager
import numpy as np

sm = SessionManager()

sample_rate = 16000
voice_audio = np.zeros(sample_rate * 6)  # 6 second audio

print("\n=== TEST 1: Voice Turn ===")
result1 = sm.send_voice_turn(voice_audio, sample_rate)
print("Pronunciation score:", result1.get("pronunciation_score"))

print("\n=== TEST 2: Mode Switch (voice -> text) ===")
switch_result = sm.toggle_mode("text")
print("Switch result:", switch_result)

print("\n=== TEST 3: Text Turn (network ON) ===")
result2 = sm.send_text_turn("Continuing in text mode now", network_online=True)
print("Text turn status:", result2.get("status"))

print("\n=== TEST 4: Short Audio (<5 sec) — score should be EMPTY ===")
short_audio = np.zeros(sample_rate * 2)
result3 = sm.send_voice_turn(short_audio, sample_rate)
print("Short audio score:", result3.get("pronunciation_score"))

print("\n=== TEST 5: Network Drop — text should be CACHED ===")
result4 = sm.send_text_turn("Message during network drop", network_online=False)
print("Status:", result4.get("status"))

print("\n=== TEST 6: Mic Lock ===")
sm.mic_hold()
result5 = sm.send_text_turn("Trying to type while mic is on")
print("Status:", result5.get("status"))
sm.mic_release()

print("\n=== TEST 7: TTS Playback (FIXED) ===")
result6 = sm.play_ai_response("This is a brand new sentence to confirm the TTS fix works properly.")
print("TTS Status:", result6)

print("\n=== FINAL SCORECARD ===")
print(sm.get_scorecard())