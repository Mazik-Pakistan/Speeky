---
name: live-call
description: >
  Codebase map for Speeky's Live Call feature — real-time two-way voice
  coaching over LiveKit (WebRTC), separate from the typed/push-to-talk voice
  pipeline. Use when working on, debugging, or explaining live voice calls,
  the LiveKit agent worker, avatar sessions, or anything under
  backend/live_call/. Auto-triggers on "live call", "LiveKit", "voice worker",
  "avatar session", "Beyond Presence", "livekit-agents".
---

# Live Call

Two-way, real-time voice coaching over LiveKit — distinct from the batch
push-to-talk pipeline (`lib/voice_ws.py`, used by pronunciation/accent
features). Runs as its own long-running process, not inside the FastAPI
request cycle.

## Backend

- `backend/routers/live_call_routes.py` — mints the LiveKit room token the
  frontend uses to join. This is the only live-call HTTP endpoint; everything
  else happens over the LiveKit room itself.
- `backend/live_call/worker.py` — the agent worker. `entrypoint()` joins the
  room, connects DB, parses `feature`/`mode`/`session_id` out of the room
  name, dispatches to a real coaching session or the idle-audience mode.
  `_prewarm()` loads Silero VAD once per worker subprocess before any job.
- `backend/live_call/dispatch.py` — `build_setup()` / `build_idle_setup()`:
  looks up the right session data and turn-handler for whichever feature
  (scenario, coaching, interview, public speaking) dispatched the call.
- `backend/live_call/stt_plugin.py` — `WhisperSTT`, wraps `lib/stt_engine.py`
  (faster-whisper) as a livekit-agents STT plugin.
- `backend/live_call/tts_plugin.py` — `PiperTTS`, wraps `lib/tts_client.py`
  (Piper) as a livekit-agents TTS plugin.
- `backend/live_call/llm_plugin.py` — `ServiceLLM`, wraps the app's own LLM
  client as a livekit-agents LLM plugin, driven by each feature's turn
  handler.

## Frontend

- `frontend/components/common/LiveCallModal.tsx` — the call UI: connecting
  state, ambient reactive orb, live captions, avatar video layout, controls.
  Dynamically imported (`next/dynamic`, `ssr: false`) since `@livekit/client`
  is ~150KB and shouldn't load until a user actually opens a call.

## Data model

No dedicated LiveCall table. A live call's turns persist into the *same*
per-feature session tables a typed session would use (`ScenarioSession`,
`CoachingSession`, `PublicSpeakingSession`, etc.) — that's deliberate, so a
Live Call session's data is identical in shape to a typed one and needs no
special-casing downstream (scoring, history, progress).

## Gotchas

- **Idle audience mode** (`mode == "idle"` in `worker.py`): used for Public
  Speaking's monologue phase. No STT, no LLM, no turn handler at all — an
  avatar the user speaks *to* that never talks back and never transcribes
  them. This is intentional, not a missing feature.
- **`initialize_process_timeout`** is set to `60.0` in `WorkerOptions`
  (default is `10.0`). On Linux, livekit-agents forks job processes from a
  `forkserver` template that only imports its preloaded plugins (torch,
  onnxruntime, av, silero) on the *first* spawn — under container CPU
  contention that cold import can exceed the 10s default and crash with a
  `TimeoutError` in `ipc/proc_pool.py`. If this fires again, it's a
  resource/timing issue, not a code bug — don't "fix" it by ripping out VAD
  prewarm or plugins.
- `docker-compose.yml`'s `livekit-agent` service reuses the `speeky-backend`
  image (`image: speeky-backend`) and just overrides the command to
  `python -m live_call.worker start` — no separate build.
- Beyond Presence avatar is env-gated (`BEY_API_KEY`); unset means audio-only,
  not a broken call.
