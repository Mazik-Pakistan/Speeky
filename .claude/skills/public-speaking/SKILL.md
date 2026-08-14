---
name: public-speaking
description: >
  Codebase map for Speeky's Public Speaking feature — deliver a speech with
  optional camera on, get pace/tone/structure/clarity scoring plus a
  MediaPipe-based camera presence read and simulated audience Q&A. Use when
  working on, debugging, or explaining public speaking sessions or the
  camera/video-analysis pipeline. Auto-triggers on "public speaking",
  "speech scoring", "video analysis", "camera presence", "MediaPipe".
---

# Public Speaking

User delivers a speech (business pitch, wedding toast, motivational,
classroom, TED-talk) via audio/text, optionally with camera on, and gets a
scorecard covering pace/tone/structure/clarity plus an optional camera-based
"physical presence" read. Some speech types also trigger a simulated
audience Q&A blended into the final score.

## Backend

- `backend/routers/public_speaking_routes.py` — `/start`, `/resume`,
  `/resume/cancel`, `/{id}/turn`, `/{id}/qa`, `/{id}/voice-ws`, `/{id}` GET,
  `/{id}/filler-words`.
- `backend/services/public_speaking_service.py` — `SPEECH_TYPES` config per
  scenario (structure elements, ideal WPM, tone/smile "register" bands);
  `start_session`/`submit_turn`/`submit_qa_response`; `_generate_scorecard`
  (orchestrates WPM, filler words, tone, structure, clarity, register, video
  scoring); `_calculate_overall_scores` (weighted blend, scenario-dependent
  weights); `_blend_qa_into_scorecard` (70/30 speech/Q&A blend, only for
  `qa_enabled` scenarios).
- `backend/lib/video_scorer.py` — turns the browser's `video_features`
  aggregate into presence sub-scores (gaze/posture/gesture/movement/
  expression) + qualitative flags/highlights. Re-derives its own coverage
  gates rather than trusting the client. **Deliberately excluded from
  `overall_score`** (its own `visual_presence` tile) so camera-on/off
  sessions stay comparable.
- `backend/lib/register_scorer.py` — scenario-conditioned tone/emotional-
  register scoring; only the voice channel feeds `tone_score`, the face
  channel stays out of the headline score for the same comparability
  reason.
- `backend/services/filler_word_service.py` — filler-word analysis. **Not
  interchangeable** with the same-named function used by `coaching_routes.py`
  — a router comment flags this as known duplication, not a bug to fix by
  merging.
- Shared audio pipeline: `relevance.py`, `session_scorer.py`,
  `recording_engine.py`, `speech_config.py`, `voice_ws.py` (uses
  `mode="full"` here — prosody + level + transcript, the only feature that
  needs live prosody).

## Frontend

- `frontend/app/dashboard/public-speaking/page.tsx` — speech-type picker +
  resume banner.
- `frontend/app/dashboard/public-speaking/[speechType]/page.tsx` —
  recording screen: voice socket, camera readiness gate, live framing/gaze
  overlays, `useVideoAnalysis` hook, submits turn + optional Q&A.
- `frontend/lib/publicSpeaking.ts` — API client, `PublicSpeakingScorecard`
  type.

### Vision stack (`frontend/lib/vision/`)

- `useVideoAnalysis.ts` — owns its own `getUserMedia({video:true})`
  (independent of the voice hook's mic stream), loads MediaPipe face/pose/
  hand landmarkers via `frameScheduler`, exposes `getVideoFeatures()` as a
  **consume-once** getter read exactly once at turn-submit time.
- `aggregator.ts` — pure/synchronous accumulator turning per-frame samples
  into the final `VideoFeatures` payload: frame-weighted percentages (gaze
  buckets, smile%, posture%) vs. dwell-gated events (away episodes,
  gestures, face-touches). Enforces `FAMILY_COVERAGE_MIN_PCT = 60%` so a
  metric is null rather than misleading when the model rarely detected
  anything.
- `headPose.ts` — head-pose angles from the MediaPipe transformation matrix,
  iris offset for gaze.
- `metrics/hands.ts` — per-hand shape (open palm, pointing, clasped,
  near-face).
- `frameScheduler.ts` — adaptive tiered inference scheduler, drops pose/hand
  models under load rather than crashing.
- `gaze.ts` — calibration-aware gaze bucket classification.

**What's actually measured** (confirmed in `architecture.md` §5.4): eye-
contact/gaze behavior, hand gesture activity/symmetry, body framing/
posture. Smile/neutral blendshapes are tracked only as a lightweight
social-signal proxy — explicitly **not** full emotion classification.

**Hand-off:** all inference runs in-browser; nothing raw (no frames, no
per-frame landmarks) is ever uploaded. `getVideoFeatures()`'s one-shot
output goes into the turn-submit payload as `video_features`, stored in
`PublicSpeakingSession.videoFeatures` (Json) and fed to
`video_scorer.score_video_session()`.

## Data model

`PublicSpeakingSession` — id/userId/speechType/inputMode/status/topic/
transcript/`scorecard: Json?`/aiQuestion/userQaResponse/`qaScore: Json?`/
`audioFeatures: Json?`/`videoFeatures: Json?`/outlierFlags/createdAt/
completedAt. Schema comment confirms: "No video, frames, or per-frame
landmarks are ever uploaded or stored."

## Gotchas

- `video_features` never contributes to `overall_score` — additive-only, to
  keep camera-on/off sessions comparable on the progress dashboard.
- Q&A blend (`QA_WEIGHT = 0.30`) rewrites `overall_score` in place but
  preserves the pre-blend number as `speech_only_score`, so it's idempotent
  across retries.
- Voice WebSocket `mode="full"` here vs. Interview Coach's
  `mode="transcript"` — don't assume the two features' voice pipelines are
  interchangeable.
