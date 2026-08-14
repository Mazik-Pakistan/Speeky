---
name: rewrite
description: >
  Codebase map for Speeky's Rewrite Lab — rewrites a spoken-response draft at
  the learner's level, scores the improvement, explains changes, and tracks
  new vocabulary until it's reused naturally. Use when working on, debugging,
  or explaining rewrite generation/scoring or vocabulary tracking. Auto-
  triggers on "rewrite", "rewrite lab", "vocab tracking", "script practice".
---

# Rewrite Lab

Two backend routers that split cleanly: `rewrite_routes.py` is a stateless
transformation engine, `rewrite_vocab_routes.py` is a separate persistent
tracking layer that consumes its output.

## Backend — Rewrite engine

- `backend/routers/rewrite_routes.py` — `POST /generate` (personalized
  rewrite + quality gate), `POST /score` (improvement scoring),
  `POST /explain` (per-change explanations), `POST /validate` (standalone
  quality gate).
- `backend/services/rewrite_service.py` — all logic. Stateless except a
  best-effort read of `db.user.learningLevel` for auto-personalization; no DB
  writes.
- `backend/lib/llm_client.py` — `chat_json` calls (Groq-backed), every
  LLM-backed function here has a deterministic offline fallback.

## Backend — Vocabulary tracking

- `backend/routers/rewrite_vocab_routes.py` — `POST /introduce`,
  `POST /refresh`, `GET /`.
- `backend/services/rewrite_vocab_service.py` — extracts advanced words a
  rewrite introduced, seeds them as "introduced", then rescans the learner's
  own `ScenarioSession`/`CoachingSession` turns to promote status
  (introduced → practicing → mastered at 3+ uses). Deliberately isolated
  from the unrelated `VocabularyWordProgress` table so unused injected words
  don't pollute that feature's stats.

## Frontend

- `frontend/app/dashboard/rewrite/page.tsx` — original/context textareas,
  difficulty selector, orchestrates generate → score+explain+introduceVocab
  in parallel.
- `frontend/lib/rewrite.ts` — API client + label maps.
- `frontend/lib/rewriteVocab.ts` — API client for vocab introduce/mastery.
- `frontend/components/dashboard/RewriteVocabPanel.tsx` — paginated vocab
  mastery panel, refetches via a bump counter after each rewrite.
- `frontend/components/dashboard/ScriptPracticePanel.tsx` — read-the-rewrite-
  aloud practice UI (baseline vs. after confidence).

## Data model

- `RewriteVocabWord` — `userId`, `word` (unique per user), `useCount`,
  `status`, `needsReview`, `introducedFrom`, `introducedAt`, `lastUsedAt`.
- `ScriptPracticeSession` — scriptText/context/status, baseline/after
  confidence+transcript+duration, `confidenceGain` — scored via the same
  `session_scorer`/`confidence_engine` audio pipeline used elsewhere.

## Gotchas

- Generation and self-validation happen in **one** LLM call per attempt
  (`_generate_and_check`), not generate-then-validate — saves tokens/rate
  limit. Up to 2 attempts, regenerating with corrective feedback on failure.
- The same rubric (`_rubric()`) backs both the in-generation self-check and
  the standalone `/validate` endpoint, so they can never disagree.
- Scoring is 0-100 where **50 means "no change,"** not "50% good" — identical
  original/rewrite text is resolved deterministically so the LLM can't score
  a no-op as a regression.
- `_recompute` (vocab mastery refresh) batches writes by target-state bucket
  via `update_many` — a prior N+1 fix (12/32/82 queries → far fewer for
  5/25/75 words), don't reintroduce per-row updates here.
