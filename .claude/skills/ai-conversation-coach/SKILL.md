---
name: ai-conversation-coach
description: >
  Codebase map for Speeky's AI Conversation Practice — open-ended, free-topic
  chat/voice practice, distinct from Coaching (fixed workplace drills) and
  Scenarios (admin-authored personas). Use when working on, debugging, or
  explaining the Conversation feature. Auto-triggers on "conversation
  practice", "AI conversation coach", "conversation session".
---

# AI Conversation Practice

Open-ended, free-topic chat practice (text or voice) — the app's general
"just talk" mode. No workplace scenario, no scripted persona.

## Backend

- `backend/routers/conversation_routes.py` — topics, session CRUD, messages,
  voice-ws, TTS, cross-session memory facts.
- `backend/services/conversation_service.py` — all logic: topic validation,
  turn handling, memory facts, session lifecycle.
- Shared libs: `backend/lib/kv_store.py` (session persistence, see below),
  `backend/lib/ai_client.py` / `llm_client.py` (Groq calls),
  `backend/lib/voice_ws.py` (voice websocket transport),
  `backend/lib/session_scorer.py` (AudioFeatures),
  `backend/lib/explore_sessions.py` (cross-feature session guard).

## Frontend

- `frontend/app/dashboard/conversation/page.tsx` — topic picker / session
  list.
- `frontend/app/dashboard/conversation/[sessionId]/page.tsx` — live chat/
  voice session UI.
- `frontend/lib/conversation.ts` — API client helpers.

## Data model

**No dedicated Prisma model** — kept out of Postgres deliberately. Session
state (turns, level, rate-limit counters, memory facts) is stored as JSON via
`KvEntry` (`backend/lib/kv_store.py`), the same pattern `interview_coach_
service`/`session_memory_service` use, since the shape is variable-length.
Search `KvEntry`/`kv_store`, not `schema.prisma`, to find the session shape.

## Gotchas

- Session interruption/auto-resume is not reimplemented here — it delegates
  to `session_memory_service` with `session_type="conversation"`.
- On `start_session`, calls `explore_sessions.supersede_open_explore_
  sessions(user_id)`, which abandons any other open session across **all
  four** "Explore-group" features (Conversation, Scenarios, Coaching,
  Interview Coach). Starting a new session anywhere silently kills stray
  open sessions in the other three — this is cross-feature behavior, don't
  assume it's scoped to just Conversation.
