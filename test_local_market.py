"""
US-48 Test Script — Local Market Interview
"""

from speeky.response import ConversationEngine
from speeky.interview_scenarios import LocalMarketInterviewSession


def main():
    conv = ConversationEngine()
    session = LocalMarketInterviewSession(conv)

    # TC-01: Standard local banking interview
    session.set_industry("Banking")
    q1 = session.get_question()
    print("\n--- TC-01: Banking Industry Question ---")
    print(q1["ai_message"])

    session.submit_answer("I always check in with my branch manager weekly to review my targets.")

    # TC-02: Unrecognized/niche industry
    session2 = LocalMarketInterviewSession(conv)
    session2.set_industry("Sialkot Sporting Goods Manufacturing")
    q2 = session2.get_question()
    print("\n--- TC-02: Niche Industry (Fallback) Question ---")
    print(q2["ai_message"])

    # TC-03: Full Urdu response
    result3 = session.submit_answer("Mujhe apni company mein bohat acha lagta hai kaam karna.")
    print("\n--- TC-03: Full Urdu Response ---")
    print(result3)

    # TC-04: Scorecard
    scorecard = session.generate_scorecard()
    print("\n--- TC-04: Scorecard ---")
    print(scorecard["summary"])

    # TC-05: Compare with generic/Western mode
    generic_question = conv.generate_response(
        "Ask me one behavioral interview question.", context_type="hr"
    )
    print("\n--- TC-05: Compare — Generic/Western Mode Question ---")
    print(generic_question)
    print("\n--- TC-05: Compare — Local Market Mode Question (from TC-01 above) ---")
    print(q1["ai_message"])


if __name__ == "__main__":
    main()