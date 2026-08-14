---
name: accent-assessment
description: >
  Codebase map for Speeky's Accent Assessment — baseline scoring against a
  target reference accent, profile tracking over time, targeted drills, and
  score disputes. Use when working on, debugging, or explaining accent
  scoring/profile/staleness. Auto-triggers on "accent assessment", "accent
  profile", "target accent", "accent staleness", "targeted drills".
---

# Accent Assessment

User picks a target reference accent (General American / British RP /
Neutral International), reads assessment passages for a baseline scored
across pronunciation/stress/rhythm/intonation/clarity, tracks that profile
over time, gets targeted drills for weak areas, can dispute a score, and
gets prompted to re-baseline when the profile goes stale.

## Shared speech pipeline

See the `pronunciation-coach` skill — this feature routes through the exact
same `audio_io.py` / `vad_engine.py` / `stt_engine.py` / `prosody_engine.py`
/ `text_alignment.py` / `speech_config.py` / `recording_engine.py` stack.

## Backend

- `backend/routers/accent_routes.py` — passage assessment submission,
  score-profile + exercises, progress-tracker, targeted-drills, sub-dialect
  dispute.
- `backend/routers/accent_assessment_routes.py` — target-accent selection,
  shared profile read, staleness check/dismiss/rebaseline, score disputes.
  **Both this and `accent_routes.py` mount at `/api/accent-assessment`** —
  a deliberate split; a router comment notes a `/profile` vs
  `/score-profile` path collision was resolved by keeping only this
  router's `/profile` live.
- `backend/routers/accent_progress_routes.py` — separate prefix,
  `/api/accent-progress`: feeds the progress-matrix UI, distinct from
  `accent_routes.py`'s `/progress-tracker`. Also feeds
  `frontend/components/dashboard/progress/AccentProgressTracker.tsx` (lives
  under `dashboard/progress/`, not `dashboard/accent-assessment/`).
- `backend/services/accent_assessment_service.py` — passage scoring, built
  directly on `recording_engine`.
- `backend/services/accent_profile_service.py`,
  `accent_tracker_service.py`, `accent_progress_service.py`,
  `accent_calibration_service.py`, `target_accent_management_service.py`,
  `targeted_exercise_service.py` — profile/exercises, progress-tracker viz,
  progress matrix, sub-dialect dispute, target-accent selection/staleness/
  disputes, and targeted-drill generation, respectively.
- `backend/lib/accent_assessment/profile_pipeline.py` — shared dataclasses
  (`AccentAssessmentResult`, `AccentProfile`) + history management via
  `kv_store`; keeps full baseline/drill history, never overwrites.
- `backend/lib/accent_assessment/target_accent_selection.py`,
  `accent_profile_staleness.py`, `score_dispute.py` — the three
  target-accent-selection/staleness/dispute feature modules, all
  KvEntry-backed.

## Frontend

- `frontend/app/dashboard/accent-assessment/page.tsx` — passage-reading
  assessment UI.
- `frontend/lib/accentAssessment.ts`, `accentCalibration.ts`,
  `accentProgress.ts` — API clients.
- `frontend/components/dashboard/AccentStalenessBanner.tsx`,
  `profile/TargetAccentSection.tsx`,
  `profile/LocalAccentCalibrationSection.tsx` — profile-page widgets.
- `frontend/components/dashboard/progress/AccentProgressTracker.tsx`,
  `AccentCheckInModal.tsx` — under `dashboard/progress/`.

## Data model

- `AccentAssessment` — per-passage attempt, full history kept; REJECTED
  rows carry no scores.
- `AccentProfile` — derived per-dimension score snapshot, linked to a
  `sourceAssessmentId`.
- `ReassessmentRequest` — re-baseline scheduling/early-retake tracking.

## Gotchas

- Two persistence layers coexist: structured Prisma rows for actual
  assessments/profiles, but target-accent preference, staleness, and
  disputes are separate `KvEntry` JSON blobs.
- Multi-voice detection in `prosody_engine.py` is an explicit heuristic
  (pitch-discontinuity between voiced runs), **not** real speaker
  diarization.
- `AccentPronunciationConfigRegistry` (in Pronunciation Coach) reads from
  this feature's `target_accent_selection.py` — a one-way dependency,
  don't add a reverse import.
