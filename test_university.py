from speeky.response import ConversationEngine
from speeky.interview_scenarios import UniversityAdmissionSession


def main():
    conv = ConversationEngine()
    session = UniversityAdmissionSession(conv)

    # TC-02: Vague degree
    r = session.set_degree("College")
    print("--- TC-02: Vague Degree ---")
    print(r)

    # TC-01: Valid degree
    session.set_degree("MBA")
    q = session.get_question()
    print("\n--- TC-01: Valid MBA Question ---")
    print(q["ai_message"])

    # TC-03: Casual tone
    r3 = session.submit_answer("Yeah I wanna hang out at your campus, seems cool.")
    print("\n--- TC-03: Casual Tone ---")
    print(r3)

    # Off-topic (E-03)
    r_offtopic = session.submit_answer("I mostly just play video games all day, nothing else really.")
    print("\n--- E-03: Off-topic ---")
    print(r_offtopic)

    # Normal answer + scorecard
    session.submit_answer("I became interested in business after running a small online store in school, which led me to want to study MBA to scale such ventures professionally.")
    scorecard = session.generate_scorecard()
    print("\n--- TC-05: Scorecard ---")
    print(scorecard["summary"])

    # TC-06: No answers edge case
    session_empty = UniversityAdmissionSession(conv)
    session_empty.set_degree("Computer Science")
    r6 = session_empty.generate_scorecard()
    print("\n--- TC-06: No Answers Edge Case ---")
    print(r6)
    assert r6["status"] == "no_answers", "FAIL: expected no_answers status"

    # TC-07: Empty/blank degree input
    session_blank = UniversityAdmissionSession(conv)
    r7 = session_blank.set_degree("   ")
    print("\n--- TC-07: Blank Degree Input ---")
    print(r7)
    assert r7["status"] == "clarify_degree", "FAIL: expected clarify_degree status"

    # TC-08: Assertions on earlier cases (sanity check)
    assert r["status"] == "clarify_degree", "FAIL: TC-02 vague degree check"
    assert r3["status"] == "casual_tone_flag", "FAIL: TC-03 casual tone check"
    assert r_offtopic["status"] == "off_topic", "FAIL: E-03 off-topic check"
    print("\n--- TC-08: All Assertions Passed ---")
    print("✅ All checks passed")


if __name__ == "__main__":
    main()