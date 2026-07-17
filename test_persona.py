from speeky.interview_persona_engine import PersonaEngine

pe = PersonaEngine()

print("\n=== TEST 1: Select Strict HR Persona ===")
result = pe.select_persona("strict_corporate_hr")
print(result)

print("\n=== TEST 2: Select Friendly Founder Persona ===")
result = pe.select_persona("friendly_startup_founder")
print(result)

print("\n=== TEST 3: Voice Pack Download Fails (E-03) ===")
result = pe.select_persona("strict_corporate_hr", voice_pack_download_success=False)
print(result)
print("Expect: status = fallback, persona = Formal Panel (default)")

print("\n=== TEST 4: TTS Slow/Latency (E-01) ===")
pe.select_persona("strict_corporate_hr")
result = pe.simulate_tts_latency_fallback(tts_service_responded_in_time=False)
print(result)
print("Expect: status = fallback, voice = default_system_voice")

print("\n=== TEST 5: User in Crisis (E-02) ===")
pe.select_persona("strict_corporate_hr")
prompt = pe.get_effective_prompt("I'm too stressed, I want to give up")
print("Prompt used:", prompt)
print("Expect: supportive prompt, NOT the strict persona prompt")

print("\n=== TEST 6: Normal Message (No Crisis) ===")
prompt = pe.get_effective_prompt("Tell me about your experience")
print("Prompt used:", prompt)
print("Expect: strict HR persona prompt (since no crisis)")

print("\n=== TEST 7: Preview Voice (US-47 Happy Path) ===")
result = pe.preview_persona_voice("friendly_startup_founder")
print(result)
print("Expect: status = ok, a preview_file path should be returned")

print("\n=== TEST 8: Preview for Invalid Persona (fallback to default) ===")
result = pe.preview_persona_voice("nonexistent_persona")
print(result)
print("Expect: status = ok, persona = Formal Panel (default), file created")

print("\n=== TEST 9: Preview Strict HR Voice ===")
result = pe.preview_persona_voice("strict_corporate_hr")
print(result)

print("\n=== TEST 10: Preview All 3 Personas (Different Voices Check) ===")
for pid in ["strict_corporate_hr", "friendly_startup_founder", "formal_panel"]:
    result = pe.preview_persona_voice(pid)
    print(f"{pid}: {result}")

print("\n=== TEST 11: Rapid Toggling (E-02, US-47) ===")
import time
now = time.time()
result_a = pe.preview_persona_voice("strict_corporate_hr", current_time=now)
result_b = pe.preview_persona_voice("friendly_startup_founder", current_time=now + 0.3)
print("Second preview halted_previous_audio:", result_b.get("halted_previous_audio"))
print("Expect: True (because it happened within 1 second of the first)")

print("\n=== TEST 12: Deprecated Persona (E-03, US-47) ===")
pe.set_favorite("friendly_startup_founder")
pe.deprecate_persona("friendly_startup_founder")
result = pe.preview_persona_voice("friendly_startup_founder")
print(result)
print("Favorite after deprecation:", pe.favorite_persona_id)
print("Expect: status=ok, persona falls back to Formal Panel, message shown, favorite cleared to None")

print("\n=== TEST 14: Fallback Voice Actually Works (Real Audio) ===")
from speeky.tts import TextToSpeech
tts = TextToSpeech()
tts.synthesize_to_file("This is the fallback voice speaking.", "output/fallback_voice_test.wav", voice="en_GB-alan-medium")
print("Check output/fallback_voice_test.wav")

import time as time_module
print("\n=== TEST 13: Preview Load Speed ===")
start = time_module.time()
pe.preview_persona_voice("formal_panel")
elapsed = time_module.time() - start
print(f"Preview generation took: {elapsed:.2f} seconds")

print("\n=== TEST 15: Persona Lock After Session Starts (TC-004) ===")
pe2 = PersonaEngine()
pe2.select_persona("strict_corporate_hr")
pe2.start_session()
result = pe2.select_persona("friendly_startup_founder")
print(result)
print("Expect: status = blocked, persona should still be Strict Corporate HR")