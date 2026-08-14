---
name: coaching
description: >
  Codebase map for Speeky's Coaching feature — structured workplace-
  communication drills (emails, roleplay, presentations) against fixed
  built-in scenario types, distinct from free-topic Conversation and
  admin-authored Scenarios. Use when working on, debugging, or explaining
  workplace coaching. Auto-triggers on "coaching", "workplace coaching",
  "coaching scenario", "workplace confidence score".
---

# Coaching (Workplace English Coaching)

Structured workplace-communication drills against a fixed set of built-in
`CoachingScenario` types, graded on professional tone/clarity/effectiveness.
No free topics (that's Conversation), no custom/admin-authored personas
(that's Scenarios).

## Backend

- `backend/routers/coaching_routes.py` — scenario list, start/turn/submit/
  session-get, voice-ws, filler-words, code-switch word tracking.
- `backend/services/coaching_service.py` — grading pipeline:
  `grade_submission()` calls the LLM for tone/clarity judgement,
  `workplace_confidence()` computes the headline 0-100 score,
  `_AGGRESSIVE`/`_find_phrases` do rule-based flag detection (also reused by
  `scenario_service`).
- Shared libs: `backend/lib/session_scorer.py` (AudioFeatures/ScoredSession),
  `backend/lib/relevance.py`, `backend/lib/prompts.py`,
  `backend/lib/explore_sessions.py`.

## Frontend

- `frontend/app/dashboard/coaching/page.tsx` — scenario type picker.
- `frontend/app/dashboard/coaching/[scenario]/page.tsx` — session UI (text or
  audio submission, roleplay turns).
- `frontend/lib/coaching.ts` — API client helpers.

## Data model

`CoachingSession` — scenario enum, inputMode, status, promptText,
submission/turns JSON, audioFeatures, and 7 separate score fields
(professionalTone, clarity, effectiveness, fluency, vocabulary,
pronunciation, confidence) + feedback/flags JSON. Enums: `CoachingScenario`,
`CoachingInputMode`, `CoachingStatus`.

## Gotchas

- Scoring is "confidence-first": `workplace_confidence()` is a weighted
  blend (tone 45% / clarity 25% / effectiveness 15% / fluency 15% for
  text-only; pronunciation added and reweighted for audio) — deliberately
  independent of raw grammar score, so grammatically-clean nonsense doesn't
  score high.
- `pronunciationScore` stays null for the text pipeline; only populated for
  audio submissions.
- Rule-based flags (aggression/profanity via `_AGGRESSIVE`/`_find_phrases`)
  run even with no LLM configured — a pure regex safety net independent of
  the grader.
