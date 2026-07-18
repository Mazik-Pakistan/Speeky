"""
US-52 Voice Test — STAR HR Interview, full audio round-trip
(AI question via TTS -> fake user answer via TTS -> ASR transcribes it -> STAR check)
"""

from speeky.response import ConversationEngine
from speeky.interview_persona_engine import PersonaEngine
from speeky.interview_scenarios import STARInterviewSession
from speeky.tts import TextToSpeech
from speeky.asr import AutomaticSpeechRecognition
import soundfile as sf


def main():
    conv = ConversationEngine()
    persona = PersonaEngine()
    persona.select_persona("strict_corporate_hr")
    session = STARInterviewSession(conv, persona)

    # Step 1: Session start — AI ka sawal (text)
    start_result = session.start()
    question_text = start_result["ai_message"]
    print(f"\nAI Question (text): {question_text}")

    # Step 2: Sawal ko awaaz mein badalna (TTS)
    tts = TextToSpeech(voice="en_GB-alan-medium")
    tts.synthesize_to_file(question_text, "output/star_question.wav")
    print("AI question audio saved to: output/star_question.wav (isko sun lo)")

    # Step 3: Fake user answer — humara sample text, TTS se awaaz mein badalte hain
    sample_answer_text = (
        "In my last job at a retail company, our team was falling behind on "
        "monthly sales targets. I was responsible for the online orders "
        "process. I redesigned the order tracking spreadsheet and trained "
        "two colleagues on it. As a result, we cut order errors by forty "
        "percent and hit our target the same month."
    )
    tts.synthesize_to_file(sample_answer_text, "output/fake_user_answer.wav")
    print("\nFake user answer audio generated: output/fake_user_answer.wav")

    # Step 4: Us generated audio ko ASR se text mein badalna
    audio_input, sample_rate = sf.read("output/fake_user_answer.wav")
    asr = AutomaticSpeechRecognition()
    transcription = asr.transcribe(audio_input, sample_rate)
    user_text = transcription["text"]
    print(f"\nASR Transcribed Text: {user_text}")

    # Step 5: STAR analysis
    result = session.submit_answer(user_text)
    print(f"\nStatus: {result['status']}")
    print(f"AI Message: {result['ai_message']}")
    print(f"STAR Analysis: {result['star_analysis']}")


if __name__ == "__main__":
    main()