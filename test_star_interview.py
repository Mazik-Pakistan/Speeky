"""
US-52 Test Script — STAR HR Behavioral Interview

Ye script Happy Path + saare Exception cases (E-01, E-02, E-03) manually
test karta hai, taake dekh sakein ke STARInterviewSession sahi kaam kar raha hai.
"""

from speeky.response import ConversationEngine
from speeky.interview_persona_engine import PersonaEngine
from speeky.interview_scenarios import STARInterviewSession


def print_result(label, result):
    print(f"\n--- {label} ---")
    print(f"Status: {result['status']}")
    print(f"AI Message: {result['ai_message']}")
    if "star_analysis" in result:
        print(f"STAR Analysis: {result['star_analysis']}")


def main():
    conv = ConversationEngine()
    persona = PersonaEngine()
    persona.select_persona("strict_corporate_hr")

    session = STARInterviewSession(conv, persona)

    # Happy Path Step 1-2: Session start, question milna
    start_result = session.start()
    print_result("SESSION START", start_result)

    # TC-01: Perfect STAR answer (sab 4 parts present)
    perfect_answer = (
        "In my last job at a retail company, our team was falling behind on "
        "monthly sales targets. I was responsible for the online orders "
        "process. I redesigned the order-tracking spreadsheet and trained "
        "two colleagues on it. As a result, we cut order errors by 40 percent "
        "and hit our target the same month."
    )
    result = session.submit_answer(perfect_answer)
    print_result("TC-01: Perfect STAR Answer", result)

    # TC-02: Missing 'Result'
    missing_result_answer = (
        "At my previous company, we had a major client complaint about late "
        "delivery. I was in charge of logistics for that account. I personally "
        "called the client and reorganized the delivery schedule."
    )
    result = session.submit_answer(missing_result_answer)
    print_result("TC-02: Missing 'Result'", result)

    # TC-03: Hypothetical answer instead of real past example
    hypothetical_answer = (
        "If that happened, I would probably talk to my manager first and then "
        "try to fix the issue as fast as possible."
    )
    result = session.submit_answer(hypothetical_answer)
    print_result("TC-03: Hypothetical Answer", result)

    # TC-04: Unprofessional complaining tone
    negative_tone_answer = (
        "Honestly my old boss was terrible, he never listened to anyone and "
        "made stupid decisions all the time, that's why everything went wrong."
    )
    result = session.submit_answer(negative_tone_answer)
    print_result("TC-04: Negative/Complaining Tone", result)

    # TC-05: Rambling — long background, no real action mentioned
    rambling_answer = (
        "So this was back when I joined the company, it was a really busy time, "
        "there were like five different departments involved and everyone had "
        "different opinions about how things should be done, and the client was "
        "based in a different city so communication was a bit tricky, and there "
        "was also a public holiday in between which delayed a few meetings, and "
        "honestly the whole situation felt very chaotic for the first couple of "
        "weeks because nobody really knew who was supposed to be doing what."
    )
    result = session.submit_answer(rambling_answer)
    print_result("TC-05: Rambling Answer", result)

    # Final Scorecard (using the perfect answer's analysis as example)
    perfect_analysis = session._analyze_with_llm(perfect_answer)
    scorecard = session.generate_scorecard(perfect_analysis)
    print("\n--- FINAL SCORECARD (Perfect Answer) ---")
    print(scorecard)


if __name__ == "__main__":
    main()