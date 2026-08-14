---
name: progress-tracking
description: >
  Codebase map for Speeky's Progress Tracking cluster — the aggregated
  confidence/fluency/vocabulary dashboard plus daily-challenge streaks,
  practice-time trophies, and vocabulary mastery tracking. Use when working
  on, debugging, or explaining the progress dashboard, streaks, practice
  time, or vocabulary drill-down. Auto-triggers on "progress dashboard",
  "streak", "daily challenge", "practice time", "trophy", "vocabulary
  mastery".
---

# Progress Tracking

Aggregates a learner's activity across every other module (baseline
assessment, conversation, coaching, scenarios, public speaking, accent,
pronunciation) into one dashboard, plus three gamification sub-systems: a
daily-challenge login streak, lifetime practice-time trophies, and per-word
vocabulary mastery.

## Backend

| File | Role |
|---|---|
| `backend/routers/progress_dashboard_routes.py` | `/progress` (rich payload) and `/overview` (flat legacy shape for Vocabulary Growth) — **intentionally different response shapes, not an alias of each other.** |
| `backend/services/progress_dashboard_service.py` | Pulls completed rows from BaselineAssessment/CoachingSession/ScenarioSession/PublicSpeakingSession/AccentAssessment, drops outlier scores, builds trend lines + the primary Confidence Score, reads streak from `daily_challenge_service`, reads practice time from `User.lifetimePracticeSeconds`, snapshots to KV for stale-fallback. |
| `backend/routers/daily_challenge_routes.py` | `/start`, `/conversation-status`, `/streak`, `/status`, `/notification`. |
| `backend/services/daily_challenge_service.py` | **Source of truth for streaks.** Starts a real AI Conversation session on the user's goal topic, times the challenge from the first prompt (5-min threshold, no turn/quality gate), credits qualified dates in KV, recomputes streaks, fires milestone notifications and the streak-warning check. |
| `backend/routers/practice_time_routes.py` | `/ping`, `/trophies`. |
| `backend/services/practice_time_service.py` | Credits lifetime practice seconds via atomic DB increment from 60s heartbeat pings (one "primary" session per user via KV registration), computes newly-unlocked hour milestones idempotently. |
| `backend/routers/vocabulary_progress_routes.py` | `/drill-down`, `/words/{word}`. |
| `backend/services/vocabulary_progress_service.py` | `record_usage()` (called from `scenario_service.end_session`) upserts `VocabularyWordProgress`, bumps `useCount`, flips to "mastered" at 3 uses, flags `needsReview` if a mastered word is later missed. |

Not part of this cluster despite living under `dashboard/progress/` on the
frontend: **targeted-drills** (`frontend/app/dashboard/progress/targeted-
drills/page.tsx`) actually calls `backend/routers/accent_routes.py` — see
the `accent-assessment` skill. `accent_progress_routes.py` and
`rewrite_vocab_routes.py`/`RewriteVocabWord` are adjacent but separate
(their own vocab table, deliberately isolated — see the `rewrite` skill).

## Frontend

- `frontend/app/dashboard/progress/page.tsx` — gated behind baseline-
  assessment access; composes `ProgressDashboardOverview`,
  `VocabularyGrowthTracker`, `PracticeTimeMilestones`,
  `AccentProgressTracker`, plus an inline Trouble Words section.
- `frontend/app/dashboard/page.tsx` — dashboard home; `DailyChallengeCard` +
  `MASTERY_METRIC_DEFS` power the Learning Mastery card.
- `frontend/components/dashboard/progress/` — `ProgressDashboardOverview.tsx`,
  `VocabularyGrowthTracker.tsx`, `VocabularyDrillDownModal.tsx`,
  `PracticeTimeMilestones.tsx`, `AccentProgressTracker.tsx`.
- `frontend/components/dashboard/DailyChallengeCard.tsx`,
  `StreakNavIcon.tsx`, `StreakWarningBanner.tsx`,
  `MilestoneCelebrationModal.tsx`.
- `frontend/lib/progressDashboard.ts`, `practiceTime.ts` (+
  `usePracticeTimePing.ts` hook), `vocabularyProgress.ts`.
- `frontend/lib/dailyChallenge.ts` vs `daily-challenge.ts` — **a real
  naming trap, not a duplicate to dedupe.** `dailyChallenge.ts` has the date
  util + status/streak/notification reads; `daily-challenge.ts` has
  challenge-start + conversation-linked status polling.

## Data model

- `User.lifetimePracticeSeconds` / `unlockedMilestoneHours`.
- `VocabularyWordProgress` (`@@unique([userId, word])`) — useCount, status
  (learning/mastered), needsReview, lastUsedAt.
- `BaselineAssessment`, `CoachingSession`, `ScenarioSession`,
  `PublicSpeakingSession`, `AccentAssessment` — source tables the dashboard
  aggregates from. **Streaks and practice time are NOT derived from these**
  — they're KV/User-column canonical sources.

## Gotchas

- Streaks live only in KV (`daily_challenge_streaks` namespace) —
  `progress_dashboard_service.get_daily_streak_days` re-reads that instead
  of deriving its own number, to avoid showing two different streaks on the
  same screen.
- Dashboard practice time is the same `User.lifetimePracticeSeconds` ping
  total as the Trophy Case, not a sum of session wall-clock spans (idle time
  would inflate it).
