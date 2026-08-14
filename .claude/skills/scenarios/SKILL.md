---
name: scenarios
description: >
  Codebase map for Speeky's Scenario-Based Learning — roleplay against
  admin-authored personas, browsable via Explore and organized by category,
  plus the admin Custom Scenario CMS (author/version/rollback). Distinct
  from Coaching (fixed drills) and Conversation (no persona). Use when
  working on, debugging, or explaining scenarios, the Explore page, or the
  custom scenario CMS. Auto-triggers on "scenario", "scenarios", "explore
  page", "custom scenario", "roleplay persona".
---

# Scenario-Based Learning

Roleplay against a defined persona/system-prompt/goal (roleplay or
negotiation), either admin-authored (Custom Scenario CMS) or built-in.
Browsable via the Explore page, organized by `Category`.

## Backend

- `backend/routers/scenario_routes.py` — learner routes (list/start/turn/
  end/recent) plus a large admin CRUD+scoring surface for `CustomScenario`
  (create/update/archive/restore/rollback/versions, quality/readiness/
  vocab-coverage/explainability/deployment-confidence scoring).
- `backend/routers/category_routes.py` — learner-facing category list +
  admin taxonomy CRUD.
- `backend/services/scenario_service.py` — session state machine + admin
  scenario lifecycle.
- `backend/services/category_service.py` — category CRUD;
  `valid_category_names()` validates `CustomScenario.category` at the
  service layer (not a DB foreign key).
- `backend/services/content_scoring_service.py`,
  `backend/services/deployment_confidence_service.py` — admin scoring
  engines called from `scenario_service`.

## Frontend

- `frontend/app/dashboard/scenarios/[key]/page.tsx` — live scenario session
  UI.
- `frontend/app/dashboard/explore/page.tsx` — discovery/browse across
  categories, plus `explore/meeting-prep/page.tsx`.
- `frontend/lib/scenario.ts` — largest of the practice-feature API clients
  (learner + admin scenario management).

## Data model

- `ScenarioSession` — turns JSON, targetVocab/vocabUsed,
  `silenceStreak`/`aggressionStreak` counters, scores (politeness/
  vocabulary/confidence), `scenarioMeta` JSON — a frozen snapshot of the
  scenario taken at session start so live admin edits don't affect an
  in-progress session.
- `CustomScenario` — persona/systemPrompt/openingLine/targetVocab/goalType/
  difficulty, versioning, plus admin scoring fields (qualityScore,
  confidenceScore, readinessScore, vocabCoverageScore,
  explainabilityReport, deploymentConfidence).
- `TemplateDeployment`, `TemplatePerformanceSnapshot`, `ContentDriftAlert`,
  `CustomScenarioVersion` — admin deployment/versioning history.
- `Category` — name/slug/icon/order/protected.
- `VocabularyWordProgress` — cross-feature word-mastery, fed by scenario
  `end_session` grading.

## Gotchas

- State machine: 3 consecutive silent/empty turns auto-closes a session; 2
  consecutive aggressive/cursing turns ends it early (`silenceStreak`/
  `aggressionStreak` in `send_turn`).
- `scenarioMeta` is a point-in-time snapshot from `start_session` — older
  rows predating this field fall back to a live lookup, don't assume it's
  always populated.
- Custom scenario "delete" is soft (archive + `archivedAt`, auto-purge grace
  window) — never a hard delete. Rolling back to an older version, however,
  **permanently deletes every version newer than it**.
- Reuses `coaching_service._AGGRESSIVE`/`_find_phrases` for flag detection —
  same rule engine as Coaching, don't duplicate it here.
