"""
US-48 Voice Test — Local Market Interview, full audio round-trip
(AI question via TTS -> fake user answer via TTS -> ASR transcribes it -> local-market check)
"""

from speeky.response import ConversationEngine
from speeky.interview_scenarios import LocalMarketInterviewSession
from speeky.tts import TextToSpeech
from speeky.asr import AutomaticSpeechRecognition
import soundfile as sf


def main():
    conv = ConversationEngine()
    session = LocalMarketInterviewSession(conv)
    session.set_industry("Banking")

    # Step 1: AI ka sawal (text)
    q_result = session.get_question()
    question_text = q_result["ai_message"]
    print(f"\nAI Question (text): {question_text}")

    # Step 2: Sawal ko awaaz mein badalna (TTS)
    tts = TextToSpeech(voice="en_GB-alan-medium")
    tts.synthesize_to_file(question_text, "output/local_market_question.wav")
    print("AI question audio saved to: output/local_market_question.wav (isko sun lo)")

    # Step 3: Fake user answer — sample text, TTS se awaaz mein badalte hain
    sample_answer_text = (
        "In my previous role at the bank, I made sure to update my branch "
        "manager every week about my progress toward my monthly deposit "
        "targets, and I always maintained a respectful and professional "
        "tone when discussing challenges with senior staff."
    )
    tts.synthesize_to_file(sample_answer_text, "output/local_market_answer.wav")
    print("\nFake user answer audio generated: output/local_market_answer.wav")

    # Step 4: Us generated audio ko ASR se text mein badalna
    audio_input, sample_rate = sf.read("output/local_market_answer.wav")
    asr = AutomaticSpeechRecognition()
    transcription = asr.transcribe(audio_input, sample_rate)
    user_text = transcription["text"]
    print(f"\nASR Transcribed Text: {user_text}")

    # Step 5: Local-market answer check
    result = session.submit_answer(user_text)
    print(f"\nStatus: {result['status']}")
    print(f"AI Message: {result['ai_message']}")


if __name__ == "__main__":
    main()