---
name: pronunciation-coach
description: >
  Codebase map for Speeky's Pronunciation Coach — per-word color-coded
  pronunciation feedback with retries and a spaced-repetition trouble-words
  bank. Use when working on, debugging, or explaining pronunciation scoring.
  Auto-triggers on "pronunciation", "pronunciation coach", "trouble words",
  "word color tier".
---

# Pronunciation Coach

User reads a target sentence aloud; gets per-word green/orange/red/gray
feedback, can retry mispronounced words, hear correct pronunciation, and
builds a cross-session "trouble words" bank with spaced repetition.

## Shared speech pipeline (also used by Accent Assessment — see that skill)

- `backend/lib/audio_io.py` — decodes uploaded audio (wav/webm/m4a/mp3 via
  PyAV) into a mono float32 waveform.
- `backend/lib/vad_engine.py` — Silero VAD: no-speech/incomplete-recording
  detection, noise-floor/SNR estimate.
- `backend/lib/stt_engine.py` — faster-whisper wrapper, word-level
  timestamps + per-word confidence.
- `backend/lib/prosody_engine.py` — praat-parselmouth pitch/intensity
  contours, syllable-nuclei rhythm proxy, heuristic multi-voice detector.
- `backend/lib/text_alignment.py` — target-vs-transcript alignment
  (difflib) + expected stress syllable via `pronouncing`/CMU dict.
- `backend/lib/speech_config.py` — single source of truth for every
  env-driven threshold/model choice (`SpeechConfig`, `load_speech_config()`).
- `backend/lib/recording_engine.py` — orchestrates all of the above into one
  "record against target text → transcript + rejection reasons + word
  classification" call. Pure analysis, no DB/HTTP.

## Backend (feature-specific)

- `backend/routers/pronunciation_coach_routes.py` — turn-scoring, 
  accessibility profile, trouble-words bank.
- `backend/routers/pronunciation_routes.py` — session lifecycle (start/
  resume/interrupt/end, submit word attempt, retry, websocket live preview,
  "hear correct pronunciation" audio). **Mounted at the same prefix,
  `/api/pronunciation-coach`, as the router above** — complementary route
  sets, not competing versions.
- `backend/services/pronunciation_coach_service.py` — implements every
  endpoint from both routers above.
- `backend/lib/pronunciation_coach/pronunciation_pipeline.py` — the one
  shared scoring pipeline. Classifies each word into a `ColorTier`
  (GREEN/ORANGE/RED/GRAY/UNSCORABLE), accent-aware config resolved per user
  via `AccentPronunciationConfigRegistry` (imports from
  `lib/accent_assessment/target_accent_selection.py` — one-directional
  dependency on the Accent Assessment feature).
- `backend/lib/pronunciation_coach/pronunciation.py` — `PronunciationScorer`
  (g2p_en phoneme alignment — a fallback, MFA isn't wired in).
- `backend/lib/pronunciation_coach/asr_adapter.py` — faster-whisper word
  timings → the pipeline's `WordAttempt` list.
- `backend/lib/pronunciation_coach/accessibility_profile.py` — opt-in
  profile exempting disclosed-condition disfluency from the fluency
  penalty, without touching color tiers.
- `backend/lib/pronunciation_coach/pronunciation_reliability.py` —
  outage/timeout retry/backoff wrapper around the pipeline.
- `backend/lib/pronunciation_coach/trouble_words.py` — tracks RED/GRAY
  outcomes over time for the spaced-repetition bank.
- `backend/lib/pronunciation_coach/confidence.py` — **dead code**,
  explicitly unused. `lib/confidence_engine.py` is what's actually wired up
  — don't confuse the two.

## Frontend

- `frontend/app/dashboard/pronunciation/page.tsx` — practice/session UI.
- `frontend/lib/pronunciation.ts` — API client mirroring
  `pronunciation_schemas.py`.
- `frontend/lib/pronunciationCoach.ts` — `scoreConversationTurn()`, shared
  by every UI surface needing turn scoring.
- `frontend/lib/usePronunciationLivePreview.ts` — live word-matching hook
  for the websocket preview, mirrors backend normalization rules.

## Data model

`PronunciationAttempt` — one row per user+sentence, **upserted not
appended** (unlimited retries, score updates in place). Session state,
trouble-words, and accessibility data have no dedicated Prisma model —
generic `KvEntry` (namespace+key+JSON) via `lib/kv_store.py`.

## Gotchas

- Every threshold in `PronunciationPipelineConfig` (green_min_score=80,
  mispronunciation_confidence_floor=60, per-repetition fluency penalty=8,
  etc.) is explicitly commented **UNCALIBRATED** — no labeled corpus exists
  yet. Don't treat these numbers as tuned.
- The phoneme-pair regional-variant tolerance logic has a "real path" that
  needs `predicted_phonemes`/`target_phonemes` — **no caller currently
  populates them**, so it always falls back to a confidence-band heuristic.
