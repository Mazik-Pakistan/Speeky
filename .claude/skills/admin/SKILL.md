---
name: admin
description: >
  Codebase map for Speeky's admin platform — role-based access, custom
  scenario CMS, categories, analytics/revenue, content intelligence, and
  tamper-evident audit logging. Use when working on, debugging, or explaining
  anything under frontend/app/dashboard/admin/ or the admin-facing backend
  routers. Auto-triggers on "admin", "audit log", "RBAC", "super admin",
  "content intelligence", "custom scenario CMS".
---

# Admin

Four access tiers: `USER` (learner, no admin access), `ADMIN`,
`COMPLIANCE`, `SUPER_ADMIN` — checked per-page against `user.role` (see
`frontend/app/dashboard/admin/*/page.tsx`, each gates on its own role check
before rendering). Exactly one account holds `SUPER_ADMIN` at a time,
enforced atomically in `user_service.transfer_super_admin`.

## Backend

- `backend/routers/user_routes.py` + `backend/services/user_service.py` —
  user listing, role promote/revoke, Super Admin transfer.
- `backend/routers/scenario_routes.py` + `backend/services/scenario_service.py`
  — Custom Scenario CMS: author/edit prompt+persona+vocabulary templates,
  sandbox preview, quality/confidence/readiness evaluation, versioning with
  rollback, archive/restore.
- `backend/routers/category_routes.py` + `backend/services/category_service.py`
  — the category taxonomy learners browse scenarios by.
- `backend/routers/analytics_routes.py` + `backend/services/analytics_service.py`
  — active users/retention/funnel/feature-usage analytics, revenue &
  reconciliation (Super Admin only), and the audit log endpoints
  (`getAuditLogs`, `verifyAuditLogIntegrity` on the frontend side) — audit
  logging lives in this router, there's no separate `audit_routes.py`.
- `backend/routers/content_intelligence_routes.py` +
  `backend/services/content_intelligence_service.py` — per-template
  performance tracking (completion/confidence/vocabulary success/
  satisfaction) with drift alerts against a template's own baseline.

## Frontend

`frontend/app/dashboard/admin/`:
- `page.tsx` — hub, role-filtered card grid linking to the sections below.
- `users/page.tsx` — promote/revoke Admin, transfer Super Admin.
- `scenarios/page.tsx` — Custom Scenario CMS (create/edit/preview/evaluate/
  rollback), embeds `components/admin/ContentIntelligencePanel.tsx`.
- `categories/page.tsx` — category CRUD.
- `analytics/page.tsx` — tabbed (overview/funnel/feature-usage/cross-filter/
  revenue), widget-based, saved-view support via
  `components/analytics/SavedViewsBar.tsx`.
- `audit-logs/page.tsx` — filterable tamper-evident log viewer + hash-chain
  integrity verification.
- `content-intelligence/page.tsx` — drift alerts and template health.

## Data model

Relevant Prisma models: `User` (role field), `Category`,
`TemplateDeployment`, `TemplatePerformanceSnapshot`, `ContentDriftAlert` —
see `backend/prisma/schema.prisma` for exact shapes; treat it as source of
truth over this doc.

## Gotchas

- Audit logs are hash-chained (each entry stores a hash of the previous one)
  — "Verify Integrity" recomputes the chain and flags any break, it's not
  just a log viewer.
- Revenue/reconciliation data is Super-Admin-gated specifically, tighter
  than the general Admin role — check `isSuperAdmin`/`isComplianceOrSuper`
  splits in the frontend pages before assuming "Admin" covers everything.
- Custom Scenario versioning: rolling back to an older version **permanently
  deletes every version newer than it** (confirmed via the rollback
  confirmation copy in `admin/scenarios/page.tsx`) — not a soft revert.
