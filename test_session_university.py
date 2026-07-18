from speeky.session_manager import SessionManager


def main():
    session = SessionManager()

    # Step 1: Start the University Admission scenario
    start_result = session.start_university_admission("MBA")
    print("--- Start University Admission (MBA) ---")
    print(start_result)

    # Step 2: Get the first question
    q = session.get_university_question()
    print("\n--- First Question ---")
    print(q["ai_message"])

    # Step 3: Send a casual-tone answer via TEXT turn, with university_admission context
    result1 = session.send_text_turn(
        "Yeah I wanna hang out at your campus, seems cool.",
        context_type="university_admission",
    )
    print("\n--- TC: Casual Tone via send_text_turn ---")
    print(result1["turn"]["ai_response"])
    assert "formal" in result1["turn"]["ai_response"].lower(), "FAIL: casual tone not routed to US-50 logic"

    # Step 4: Send an off-topic answer via TEXT turn
    result2 = session.send_text_turn(
        "I mostly just play video games all day, nothing else really.",
        context_type="university_admission",
    )
    print("\n--- TC: Off-topic via send_text_turn ---")
    print(result2["turn"]["ai_response"])
    assert "academic" in result2["turn"]["ai_response"].lower(), "FAIL: off-topic not routed to US-50 logic"

    # Step 5: Send a normal academic answer
    result3 = session.send_text_turn(
        "I became interested in business after running a small online store in school.",
        context_type="university_admission",
    )
    print("\n--- TC: Normal Answer via send_text_turn ---")
    print(result3["turn"]["ai_response"])

    # Step 6: Sanity check - a DIFFERENT context_type should NOT use US-50 logic
    result4 = session.send_text_turn(
        "hello there",
        context_type="general",
    )
    print("\n--- TC: General context (should NOT be US-50 flavored) ---")
    print(result4["turn"]["ai_response"])

# Play the AI's response as actual audio (US-38 + US-50 combined)
    audio_result = session.play_ai_response(
        result1["turn"]["ai_response"],
        output_path="output/university_test_reply.wav"
    )
    print("\n--- TC: Voice Playback ---")
    print(audio_result)

    print("\n✅ All routing checks passed")


if __name__ == "__main__":
    main()