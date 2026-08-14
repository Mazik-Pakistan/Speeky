---
name: interview-coach
description: >
  Codebase map for Speeky's Interview Coach — practice job interviews
  (standard/panel/case-study/multi-round) via text or voice, graded
  scorecard, mentor peer-review sharing. Use when working on, debugging, or
  explaining interview sessions or peer review. Auto-triggers on "interview
  coach", "interview session", "peer review", "mentor review".
---

# Interview Coach

Practice job interviews (standard/panel/case-study/multi-round "Interview
Day") via text or voice with an AI interviewer, get a graded scorecard, and
optionally share the session with a mentor for asynchronous peer-review
comments.

## Backend

- `backend/routers/interview_coach_routes.py` — thin route registration:
  `/sessions*` (start/answer/pause/resume/break/end/voice-ws/filler-words)
  and `/reviews*` (share/comments/revoke/report).
- `backend/services/interview_coach_service.py` — all logic: session state
  machine (nested dict, one KV blob per session), per-mode question
  generation, behavioral flag detection (rambling/one-word/silence/jumped-
  to-number/vague-technical-answer), LLM-based answer grading
  (`_grade_answers`, one call per **session**, not per turn), per-mode
  scoring, mentor/peer-review sharing (`_share_review`, `_add_peer_comment`,
  `_report_comment` with a 2-report author block).
- `backend/lib/kv_store.py` — sessions/shares/comments each in their own
  namespace (`interview_coach_sessions`/`_shares`/`_comments`) — **no
  Prisma table for this feature at all.**
- `backend/lib/relevance.py` — deterministic substance gate + relevance
  scoring, used before/alongside LLM grading.
- `backend/lib/voice_ws.py` — voice mode uses `mode="transcript"`
  (transcript only, no live prosody — contrast with Public Speaking's
  `mode="full"`).
- `backend/lib/interview_scenarios/` — static scenario data (case-study
  prompts, panel personas).

## Frontend

- `frontend/app/dashboard/interview-coach/page.tsx` — setup: pick mode/
  tone/panelists/case type/rounds, start session, resume banner.
- `frontend/app/dashboard/interview-coach/[sessionId]/page.tsx` — live
  screen: text/voice turns, pause/resume/break, lazy-loaded LiveKit modal,
  end session, scorecard + filler-word breakdown, "Share for review".
- `frontend/app/dashboard/interview-coach/reviews/[shareId]/page.tsx` — the
  mentor-facing peer-review flow: opens by share link, shows a comment
  thread only (no transcript view yet — flagged as a known gap in the
  page's own info banner), post/report comments.
- `frontend/lib/interviewCoach.ts` — API client (start/submit/pause/resume/
  end/share/comments).

## Data model

None dedicated — entirely `KvEntry`-backed via `lib/kv_store.py`.

## Gotchas

- Scoring is LLM-graded per answer, not a heuristic that starts at 85 and
  subtracts (an earlier approach, explicitly replaced). `None` from the
  grader means "grader unavailable" — distinct from a real 0, don't collapse
  the two.
- Peer-review shares have three states (expired/revoked/active), checked in
  `_get_active_share`; only the share creator can revoke.
- Case-study mode has its own turn-handling branch
  (`_handle_case_study_turn`) with flags (`jumped_to_number`,
  `clarifying_question`) that don't exist in other modes.
