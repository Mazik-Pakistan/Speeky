# Speeky

Speeky is an AI communication coaching platform with a **Next.js frontend** and a **FastAPI backend**. It supports guided communication practice across interviews, workplace conversations, public speaking, pronunciation, accent assessment, rewriting, and progress tracking.

This README is written for both humans and LLMs: it gives a high-signal map of what exists, where it lives, and how parts connect.

## Repository Layout

- `/home/runner/work/Speeky/Speeky/frontend` — Next.js 14 app (App Router, TypeScript, Tailwind)
- `/home/runner/work/Speeky/Speeky/backend` — FastAPI service (Python 3.11+, Prisma client for Postgres)

## Product Capabilities (Current)

- Authentication: signup/login/logout/refresh/reset password
- Dashboard and role-aware navigation
- Baseline assessment and gated feature access
- AI Conversation Practice (topics, sessions, transcript review, TTS endpoint)
- Workplace coaching scenarios
- Interview coach flows and peer review sharing
- Resume/JD intake and mismatch checking
- Session memory and interruption/resume flows
- Pronunciation coach (sentence-level upload + word-level feedback)
- Accent assessment + accent profile + targeted exercises
- Public speaking practice sessions
- Rewrite lab features (rewrite + vocabulary)
- Progress dashboards, streak/notifications, and admin surfaces

## Tech Stack

### Frontend (`/frontend`)
- Next.js 14, React 18, TypeScript
- Tailwind CSS + custom UI components
- Context-based client state (`AuthContext`, `AssessmentContext`, `ActiveSessionsContext`, `ThemeContext`)
- API wrapper with automatic refresh-token retry handling (`lib/api.ts`)
- Live features use browser media APIs plus LiveKit/WebSocket integrations

### Backend (`/backend`)
- FastAPI + Uvicorn
- Prisma Client Python (`prisma-client-py`) over PostgreSQL
- JWT cookie auth (access + refresh, rotation + reuse detection)
- LLM integration via Groq-compatible API with offline fallbacks
- Audio pipeline: PyAV, faster-whisper, Silero VAD, parselmouth, Piper TTS
- SlowAPI global rate limiting + feature-specific throttles

## Key Entry Points

### Frontend
- App root layout: `/home/runner/work/Speeky/Speeky/frontend/app/layout.tsx`
- Global providers: `/home/runner/work/Speeky/Speeky/frontend/app/providers.tsx`
- Dashboard shell: `/home/runner/work/Speeky/Speeky/frontend/app/dashboard/layout.tsx`
- API client: `/home/runner/work/Speeky/Speeky/frontend/lib/api.ts`

### Backend
- App bootstrap: `/home/runner/work/Speeky/Speeky/backend/main.py`
- Route layer: `/home/runner/work/Speeky/Speeky/backend/routers`
- Business logic layer: `/home/runner/work/Speeky/Speeky/backend/services`
- Shared engines/utils: `/home/runner/work/Speeky/Speeky/backend/lib`
- Data model: `/home/runner/work/Speeky/Speeky/backend/prisma/schema.prisma`

## API Surface (High-Level)

Backend mounts these router prefixes in `main.py`:

- `/api/auth`, `/api/users`
- `/api/categories`, `/api/analytics`, `/api/active-sessions`
- `/api/assessment`, `/api/progress-dashboard`, `/api/practice-time`
- `/api/coaching`, `/api/conversation`, `/api/scenarios`
- `/api/interview-coach`, `/api/resume-jd-intake`, `/api/session-memory`
- `/api/pronunciation-coach`, `/api/accent-assessment`, `/api/accent-progress`
- `/api/public-speaking`, `/api/daily-challenge`, `/api/code-switch`
- `/api/rewrite`, `/api/rewrite-vocab`, `/api/vocabulary-progress`
- `/api/notifications`, `/api/overuse`

Uploads are served from `/uploads`.

## Data Model (High-Level)

Important Prisma models include:

- Identity/Auth: `User`, `RefreshToken`, `PasswordResetToken`, `SignupOtp`, `EmailChangeOtp`
- Coaching/Practice: `CoachingSession`, `ScenarioSession`, `PublicSpeakingSession`, `KvEntry`
- Assessment/Progress: `BaselineAssessment`, `PronunciationAttempt`, `AccentAssessment`, `AccentProfile`, `ReassessmentRequest`
- Content/Admin/Signals: `Category`, `TemplateDeployment`, `TemplatePerformanceSnapshot`, `ContentDriftAlert`, `LivenessFlag`, others

Use the schema file as source of truth.

## Local Development

## 1) Backend

From `/home/runner/work/Speeky/Speeky/backend`:

1. Create env from `.env.example` and fill required values.
2. Install dependencies:
   - `uv sync`
3. Generate Prisma client:
   - `uv run prisma generate`
4. Apply migrations (fresh DB):
   - `uv run prisma migrate deploy`
5. Run backend:
   - `uv run python main.py`
6. Optional tests:
   - `uv run pytest`

Docs and health:
- `http://localhost:8000/docs`
- `http://localhost:8000/health`

## 2) Frontend

From `/home/runner/work/Speeky/Speeky/frontend`:

1. Create env from `.env.example`:
   - `NEXT_PUBLIC_APP_API_URL=http://localhost:8000/api`
2. Install deps:
   - `npm install`
3. Run dev server:
   - `npm run dev`
4. Optional checks:
   - `npm run lint`
   - `npm run build`
   - `npm run test:unit`

## AI/LLM Handoff Notes

If another team feeds this repo to an LLM, include at minimum:

1. This root README
2. `/home/runner/work/Speeky/Speeky/architecture.md`
3. `/home/runner/work/Speeky/Speeky/backend/README.md`
4. `/home/runner/work/Speeky/Speeky/backend/prisma/schema.prisma`
5. `/home/runner/work/Speeky/Speeky/backend/main.py`
6. `/home/runner/work/Speeky/Speeky/frontend/app/dashboard/layout.tsx`
7. `/home/runner/work/Speeky/Speeky/frontend/lib/api.ts`

This set gives an LLM enough context to reason about architecture, APIs, state, auth, and extension points with high fidelity.
