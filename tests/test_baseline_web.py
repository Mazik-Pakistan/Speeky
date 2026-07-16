"""
Web-interface test harness for Baseline Assessment & Confidence Scoring.

Drives the same doc test cases (TC-xxx) as tests/test_baseline_direct.py, but
purely over HTTP against a *running* Flask instance of web_app.py -- this is
the "test the web interface separately" half. It does not import the speeky
package at all; it only talks to the server, the same way a browser would.

Usage:
    1. In one terminal:  .venv_test\\Scripts\\python.exe web_app.py
    2. In another:       .venv_test\\Scripts\\python.exe tests\\test_baseline_web.py

The app keeps ONE global demo user (see web_app.py's get_or_create_demo_user),
so this script resets/skips between scenarios rather than creating new users --
there is no multi-user support in the web layer to test against.
"""

import sys
import requests

BASE = "http://127.0.0.1:5000"
PASS, FAIL = [], []


def check(tc_id, description, condition):
    if condition:
        PASS.append((tc_id, description))
        print(f"[PASS] {tc_id}: {description}")
    else:
        FAIL.append((tc_id, description))
        print(f"[FAIL] {tc_id}: {description}")


def reset(session):
    session.post(f"{BASE}/assessment/reset")


def submit_all(session, answers):
    """POST each answer in turn, returning the final (completed) JSON response."""
    last = None
    for a in answers:
        last = session.post(f"{BASE}/assessment/submit", json=a).json()
    return last


GOOD_ANSWERS = [
    {"response_type": "text", "text_data": "I usually wake up early and go for a run before work."},
    {"response_type": "text", "text_data": "My main goal is to communicate more confidently in meetings."},
    {"response_type": "text", "text_data": "Persistence combined with clear communication drives success."},
    {"response_type": "text", "text_data": "I resolved a conflict between teammates by hearing both sides."},
    {"response_type": "text", "text_data": "I enjoy hiking on weekends to clear my mind and stay active."},
]

try:
    ping = requests.get(BASE + "/", timeout=3)
except requests.exceptions.ConnectionError:
    print(f"Cannot reach {BASE} -- start the server first:\n"
          f"    .venv_test\\Scripts\\python.exe web_app.py")
    sys.exit(1)

s = requests.Session()
reset(s)

# --- BAS-US-09 / BAS-US-01: full text assessment through the real routes ---
print("\n=== BAS-US-09 / BAS-US-01 via HTTP ===")
r = s.get(f"{BASE}/assessment/start")
check("BAS-US-09 (start)", "GET /assessment/start begins a session (matches index.html's apiCall, which is a GET)",
      r.status_code == 200 and "/assessment" in r.url)

q = s.get(f"{BASE}/assessment/question").json()
check("BAS-US-09 (question)", "First question is served", q.get("success") and q.get("current_question"))

final = submit_all(s, GOOD_ANSWERS)
check("BAS-US-09 TC-002", "Text assessment completes with pronunciation N/A",
      final["status"] == "completed" and final["result"]["pronunciation_score"] is None)

aid = final["result"]["assessment_id"]
r = s.get(f"{BASE}/results/{aid}")
check("BAS-US-01 TC-001", "Results page renders 200 with the completed assessment",
      r.status_code == 200 and "Confidence Score" in r.text)

# --- BAS-US-06 breakdown, reachable right after baseline completes ---
breakdown = s.get(f"{BASE}/api/confidence").json()
check("BAS-US-06", "Confidence breakdown is non-empty immediately after baseline (not the empty-history placeholder)",
      breakdown["current_score"] > 0 and "Complete the Initial" not in breakdown["explanation"])

# --- BAS-US-02: feature gating flips to full access post-completion ---
features = s.get(f"{BASE}/api/features").json()
check("BAS-US-02", "Full access unlocked immediately after baseline completes",
      features["access_level"] == "full_access" and features["inaccessible_features"] == [])

# --- BAS-US-02: skip flow on a reset (unassessed) user ---
print("\n=== BAS-US-02: Skip flow via HTTP ===")
reset(s)
features = s.get(f"{BASE}/api/features").json()
check("BAS-US-02 TC-003", "Reset user is locked out of gated features again",
      features["access_level"] == "basic_only"
      and "interview_coach" in features["inaccessible_features"])

skip = s.post(f"{BASE}/assessment/skip", json={}).json()
check("BAS-US-02 TC-001/TC-002", "Skip confirms in one call (route auto-confirms) -> status unassessed",
      skip.get("status") == "unassessed")

# --- BAS-US-03: integrity flags surface through submit ---
print("\n=== BAS-US-03: Integrity checks via HTTP ===")
reset(s)
s.get(f"{BASE}/assessment/start")
r = s.post(f"{BASE}/assessment/submit",
           json={"response_type": "text", "text_data": "irrelevant", "clipboard_detected": True}).json()
check("BAS-US-03 TC-002", "Clipboard-pasted answer is flagged via the real submit route",
      r["previous_result"]["is_flagged"] and r["previous_result"]["flag_reason"] == "Clipboard paste detected")

r = s.post(f"{BASE}/assessment/submit",
           json={"response_type": "text", "text_data": "a a a a a a a a"}).json()
check("BAS-US-03 (gibberish)", "Gibberish short-word answer is flagged via the real submit route",
      r["previous_result"]["is_flagged"])

reset(s)

# --- BAS-US-12: eligibility endpoint ---
print("\n=== BAS-US-12: Re-assessment eligibility via HTTP ===")
s.get(f"{BASE}/assessment/start")
submit_all(s, GOOD_ANSWERS)
elig = s.get(f"{BASE}/api/reassessment/eligibility").json()
check("BAS-US-12 (not yet eligible)", "Fresh baseline reports ~30 days until next eligible re-assessment",
      elig["is_eligible"] is False and elig["days_until_eligible"] == 30)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed\n{'='*60}")
if FAIL:
    print("FAILED:")
    for tc, desc in FAIL:
        print(f"  - {tc}: {desc}")
    sys.exit(1)
