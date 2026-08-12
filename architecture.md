# Speeky Architecture

This document is an implementation-level architecture reference for future teams and LLM-based assistants.

## 1. System Context

Speeky is a two-tier web application:

- **Frontend**: Next.js app in `/home/runner/work/Speeky/Speeky/frontend`
- **Backend**: FastAPI app in `/home/runner/work/Speeky/Speeky/backend`
- **Primary DB**: PostgreSQL via Prisma schema/client
- **External/optional AI services**: Groq (LLM), LiveKit (live call transport), Bey avatar plugin, Piper model assets

## 2. Runtime Topology

```text
Browser (Next.js client)
  ├─ HTTP(S) JSON -> FastAPI /api/*
  ├─ multipart/form-data -> FastAPI upload endpoints
  ├─ WebSocket PCM audio -> feature voice-ws endpoints
  └─ reads avatar/media -> /uploads/*

FastAPI app (main.py)
  ├─ Routers (API boundary)
  ├─ Services (business logic)
  ├─ Lib engines (LLM/audio/scoring/safety/helpers)
  └─ Prisma client -> PostgreSQL
```

## 3. Backend Architecture

## 3.1 App bootstrap and middleware

Source: `/home/runner/work/Speeky/Speeky/backend/main.py`

- Initializes FastAPI app with lifespan hooks
- Connects/disconnects Prisma DB client during startup/shutdown
- Applies:
  - CORS middleware (origins from `CLIENT_ORIGIN`)
  - SlowAPI rate-limiter middleware (global default `100/minute`)
  - null-byte request guard
  - typed/global exception handlers
- Mounts static uploads directory at `/uploads`
- Mounts all feature routers under `/api/*`

## 3.2 Layering model

```text
Router (transport + auth dependency + request/response shape)
  -> Service (feature orchestration + business rules)
     -> Lib helpers/engines (cross-feature primitives)
        -> Prisma models or external APIs
```

### Router layer
- Location: `/home/runner/work/Speeky/Speeky/backend/routers`
- Responsibility: endpoint wiring, request parsing, dependency injection

### Service layer
- Location: `/home/runner/work/Speeky/Speeky/backend/services`
- Responsibility: feature workflows and domain logic

### Shared lib layer
- Location: `/home/runner/work/Speeky/Speeky/backend/lib`
- Notable modules:
  - `llm_client.py`, `ai_client.py`, `prompts.py`
  - `pii.py`, `content_safety.py`
  - `recording_engine.py` and speech pipeline modules (`audio_io.py`, `vad_engine.py`, `stt_engine.py`, `prosody_engine.py`, `text_alignment.py`)
  - `session_scorer.py`, `confidence_engine.py`
  - `kv_store.py` (structured access over `KvEntry` table)

## 3.3 Backend domain modules (by route prefix)

- `/api/auth`, `/api/users` — identity, profile, role and avatar management
- `/api/assessment` — baseline/reassessment and gating access state
- `/api/conversation` — conversation sessions, messages, memory, transcript, TTS
- `/api/coaching` — workplace communication coaching scenarios
- `/api/interview-coach` — interview sessions and peer review workflows
- `/api/resume-jd-intake` — resume/JD intake and mismatch analysis
- `/api/session-memory` — interruption recovery and profile memory
- `/api/pronunciation-coach` — sentence audio attempts + word-level feedback
- `/api/accent-assessment` and `/api/accent-progress` — passage scoring, accent profile, follow-up exercises
- `/api/public-speaking` — speech practice sessions and evaluations
- `/api/scenarios`, `/api/categories`, `/api/code-switch`, `/api/rewrite`, `/api/rewrite-vocab`, `/api/daily-challenge`, `/api/progress-dashboard`, `/api/vocabulary-progress`, `/api/notifications`, `/api/overuse`, `/api/practice-time`, `/api/analytics`, `/api/active-sessions`

## 3.4 Persistence model

Source of truth: `/home/runner/work/Speeky/Speeky/backend/prisma/schema.prisma`

Patterns used:

1. **Relational entities** for identities, sessions, assessments, admin/config
2. **`KvEntry` key-value rows** for variable-shaped state in session-oriented features
3. **Token/security tables** for refresh rotation and reset/OTP flows

Representative models:
- `User`
- `BaselineAssessment`, `PronunciationAttempt`, `AccentAssessment`, `AccentProfile`
- `ScenarioSession`, `CoachingSession`, `PublicSpeakingSession`
- `RefreshToken`, `PasswordResetToken`, `SignupOtp`, `EmailChangeOtp`
- `KvEntry`

## 3.5 Security model

- JWT cookie auth:
  - access token cookie for authenticated API calls
  - refresh token cookie scoped to auth endpoints
- Refresh token rotation + reuse detection
- Role-based access in auth middleware/dependencies
- Password and token hashing before persistence
- Rate limiting and structured app errors
- PII redaction before LLM-bound processing

## 4. Frontend Architecture

## 4.1 Application shell

Key files:
- `/home/runner/work/Speeky/Speeky/frontend/app/layout.tsx`
- `/home/runner/work/Speeky/Speeky/frontend/app/providers.tsx`
- `/home/runner/work/Speeky/Speeky/frontend/app/dashboard/layout.tsx`

Behavior:
- Root layout loads local fonts, global styles, and providers
- Providers wrap app with Theme + Auth contexts and toast notifications
- Dashboard layout enforces auth, applies feature gates, and renders shared shell (sidebar/header/banners)

## 4.2 Client state and context boundaries

Context modules in `/home/runner/work/Speeky/Speeky/frontend/contexts`:

- `AuthContext`: authenticated user lifecycle and logout
- `AssessmentContext`: assessment access status for UI gating
- `ActiveSessionsContext`: resumable session indicators
- `ThemeContext`: dark/light theme preference

State philosophy:
- Keep cross-route session/auth state in contexts
- Keep feature data access in `frontend/lib/*` API modules

## 4.3 Route organization

`/frontend/app` includes:
- Public surfaces: landing, login/signup/reset-password, legal pages
- Protected surfaces: `/dashboard/*` feature pages
- Admin surfaces: `/dashboard/admin/*`

Feature pages are mostly client components and consume typed API helpers from `frontend/lib`.

## 4.4 Frontend–backend contract

Source: `/home/runner/work/Speeky/Speeky/frontend/lib/api.ts`

- Base API URL from `NEXT_PUBLIC_APP_API_URL`
- Sends credentials (`cookies`) on all requests
- Uniform API helper for JSON and FormData requests
- On 401 for non-auth routes: attempts one shared refresh call, retries once, then emits `speeky:session-expired`
- Normalizes inconsistent backend error envelope shapes into one thrown `ApiError`

## 5. AI and Speech Pipeline

## 5.1 LLM pattern

For LLM-backed features, backend uses a wrapper pattern:

```text
Service -> prompt builder (lib/prompts.py) -> ai_client/llm_client
```

Design intent:
- Groq/OpenAI-compatible remote inference when configured
- deterministic/local fallback behavior when API keys are unavailable
- shared safety and validation around generated content

## 5.2 Recording/voice analysis pattern

Core recording pipeline is composed in `lib/recording_engine.py` from:

1. audio decoding and waveform stats
2. VAD segmentation and quality checks
3. STT transcript + timing/confidence
4. prosody extraction
5. transcript/target alignment and scoring

Used heavily by pronunciation and accent-assessment endpoints.

## 5.3 Real-time voice mode

Backend supports voice WebSocket flows where client streams raw PCM audio and backend segments/transcribes utterances. Client keeps user-in-the-loop before message send (transcribed text is reviewable).

## 6. Request Lifecycles (Canonical)

## 6.1 Authenticated API request

```text
Frontend page -> lib/api.ts -> /api/* request with cookies
  if 401 (non-auth route): POST /api/auth/refresh once
    if refresh success: retry original request once
    else: signal session-expired
```

## 6.2 Pronunciation attempt

```text
Client uploads audio (multipart)
  -> pronunciation router/service
  -> recording_engine speech pipeline
  -> scoring + weak-point extraction
  -> upsert/rewrite attempt record
  -> structured feedback response
```

## 6.3 Accent assessment completion

```text
Client uploads passage audio
  -> accent assessment pipeline
  -> quality gate + multidimensional scoring
  -> store assessment attempt
  -> if completed: generate/update accent profile + exercises
```

## 7. Configuration and Environment

### Frontend
- `.env.example` exposes `NEXT_PUBLIC_APP_API_URL`

### Backend
- `.env.example` defines DB/JWT/SMTP/Groq/LiveKit/Bey/speech tuning vars
- speech thresholds centralize in `lib/speech_config.py`

Operational rule: keep env-driven behavior in config modules; avoid hardcoding model/threshold values inside services.

## 8. Extension Guidance

When adding a new capability:

1. Add/extend Prisma schema first when persistence is needed
2. Add service module for business logic
3. Expose through a thin router with explicit request/response schema
4. Add frontend API helper in `frontend/lib`
5. Integrate UI route/page and dashboard navigation if needed
6. Reuse existing cross-cutting modules (auth, error handling, pii, scoring) before introducing new patterns

## 9. Known Architectural Constraints

- Some backend response envelopes vary by feature; frontend `extractErrorMessage` already compensates
- Voice/LLM features may degrade to fallback behavior when optional integrations are unavailable
- `KvEntry` enables agility but requires strict key naming/versioning discipline in services
- Frontend relies on cookie auth; CORS and credential settings must remain aligned across environments

## 10. Fast Orientation Checklist for New Teams/LLMs

Read in this order:

1. `/home/runner/work/Speeky/Speeky/README.md`
2. `/home/runner/work/Speeky/Speeky/backend/main.py`
3. `/home/runner/work/Speeky/Speeky/backend/prisma/schema.prisma`
4. `/home/runner/work/Speeky/Speeky/backend/README.md`
5. `/home/runner/work/Speeky/Speeky/frontend/app/layout.tsx`
6. `/home/runner/work/Speeky/Speeky/frontend/app/dashboard/layout.tsx`
7. `/home/runner/work/Speeky/Speeky/frontend/lib/api.ts`

That sequence gives complete architecture context with minimal token budget.
