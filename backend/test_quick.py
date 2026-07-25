"""
Quick manual test for actionable_script_service.
Run from the backend folder:  python test_quick.py

- Type or paste your submission text when prompted
- Press Enter twice when done typing
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env so GROQ_API_KEY is picked up
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from schemas.actionable_script_schemas import ProcessScriptRequest
from services import actionable_script_service


def get_multiline_input(prompt: str) -> str:
    print(prompt)
    print("(Press Enter twice when done)\n")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


async def main():
    submission = get_multiline_input("Paste your text below:")

    if not submission:
        print("[ERROR]: No input provided.")
        return

    scenario = input("\nScenario context (optional, press Enter to skip): ").strip()
    language = input("Language (default: en): ").strip() or "en"

    payload = ProcessScriptRequest(
        submission=submission,
        scenario_context=scenario or None,
        language=language,
    )

    print("\n[Processing...]\n")

    result = await actionable_script_service.process_script(payload)

    from fastapi.responses import JSONResponse
    if isinstance(result, JSONResponse):
        import json
        body = json.loads(result.body)
        print(f"[ERROR {result.status_code}]: {body}")
        return

    print(f"[OK] script_id          : {result.script_id}")
    print(f"     baseline_status    : {result.baseline_status}")
    print(f"     category           : {result.category}")
    print(f"     rewrite_status     : {result.rewrite_status}")

    if result.baseline_scores:
        print("\n[Baseline Scores]")
        for field, val in result.baseline_scores.model_dump().items():
            print(f"   {field:<20}: {val}")

    print("\n[Polished Rewrite]")
    print(result.polished_rewrite or "(none - LLM not configured or rewrite failed)")

    if result.rewrite_note:
        print(f"\n[Note]: {result.rewrite_note}")

    if result.newly_introduced_words:
        print(f"\n[New words added]: {', '.join(result.newly_introduced_words)}")


asyncio.run(main())
