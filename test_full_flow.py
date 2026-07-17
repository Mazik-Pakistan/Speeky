import requests
from speeky.interview_persona_engine import PersonaEngine, PERSONAS
from speeky.tts import TextToSpeech

pe = PersonaEngine()

# Har persona ke liye alag sample message (asli user jaisa)
sample_messages = {
    "strict_corporate_hr": "Why should we hire you over other candidates?",
    "friendly_startup_founder": "Why should we hire you over other candidates?",
    "formal_panel": "Why should we hire you over other candidates?",
}

for persona_id, user_message in sample_messages.items():
    print(f"\n{'='*60}")
    print(f"PERSONA: {PERSONAS[persona_id]['name']}  (voice: {PERSONAS[persona_id]['voice']})")
    print(f"{'='*60}")

    # Step A: Preview sunwao (fixed sample)
    preview_result = pe.preview_persona_voice(persona_id)
    print(f"Preview file: {preview_result.get('preview_file')}")

    # Step B: Persona select karo
    pe.select_persona(persona_id)
    active = pe.get_active_persona()

    # Step C: User ka sawal bhejo, persona ke tone ke hisaab se AI jawab de
    tone_prompt = pe.get_effective_prompt(user_message)
    print(f"User asked: {user_message}")
    print("Thinking...")

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "system": tone_prompt,
                "prompt": user_message,
                "stream": False
            },
            timeout=180
        )
        ai_reply = response.json().get("response", "")
        print(f"AI Reply: {ai_reply[:300]}...")

        # Step D: Isi persona ki awaaz mein jawab bolo
        tts = TextToSpeech()
        output_file = f"output/fullflow_{persona_id}.wav"
        tts.synthesize_to_file(ai_reply, output_file, voice=active["voice"])
        print(f"Reply audio saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")

print(f"\n{'='*60}")
print("DONE. Ab teeno fullflow_*.wav files sunno — har ek alag awaaz")
print("aur alag tone/style mein jawab de raha hona chahiye.")
print(f"{'='*60}")

print("\n" + "="*60)
print("CRISIS TEST: User expresses distress mid-interview")
print("="*60)

pe.select_persona("strict_corporate_hr")
crisis_message = "I'm too stressed, I want to give up on this interview."

tone_prompt = pe.get_effective_prompt(crisis_message)
print(f"User said: {crisis_message}")
print("Thinking...")

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.1:8b",
        "system": tone_prompt,
        "prompt": crisis_message,
        "stream": False
    },
    timeout=180
)
ai_reply = response.json().get("response", "")
print(f"AI Reply: {ai_reply}")

tts = TextToSpeech()
output_file = "output/crisis_response.wav"
tts.synthesize_to_file(ai_reply, output_file, voice="en_GB-alan-medium")
print(f"\nAudio saved to: {output_file}")
print("Listen to this — it should sound calm/supportive, NOT strict/aggressive.")