---
name: resume-jd
description: >
  Codebase map for Speeky's Resume/JD Matching feature — upload a resume,
  paste a job description, flag keyword mismatch. Use when working on,
  debugging, or explaining resume parsing, JD intake, or mismatch checking.
  Auto-triggers on "resume", "job description", "JD", "resume-jd", "mismatch
  check".
---

# Resume/JD Matching

User uploads a resume (PDF/DOCX/TXT), pastes a job description, and gets a
keyword-overlap mismatch flag — used to steer the interview-coach question
generator toward transferable skills when there's a gap.

## Backend

- `backend/routers/resume_jd_routes.py` — `POST/GET /resumes`,
  `GET /resumes/{id}`, `POST /jds`, `GET /jds/{id}`, `POST /mismatch-check`.
- `backend/services/resume_jd_service.py` — all logic in one file: file
  extraction, PII redaction, JD truncation, keyword overlap scoring.
- `backend/lib/pii.py` — redacts extracted resume text before storage/LLM
  exposure.
- `backend/lib/kv_store.py` — **this feature has no Prisma model.** Resumes
  and JDs are stored as plain KV rows (`resume_jd_resumes` / `resume_jd_jds`
  namespaces), not SQL tables. Ownership is enforced manually
  (`resume["user_id"] != user_id` checks) since there's no DB-level FK/RLS.

## Frontend

- `frontend/app/dashboard/resume-jd/page.tsx` — upload UI, JD paste box,
  resume/JD pickers, mismatch-check trigger and result display.
- `frontend/lib/resumeJd.ts` — API client (`uploadResume`, `listResumes`,
  `submitJd`, `checkMismatch`) + result types.
- `frontend/components/dashboard/ExploreResumeBanner.tsx` — surfaces
  resume/JD context in other flows (e.g. interview coach).

## Gotchas

- File parsing: `pypdf.PdfReader` for PDFs, `python-docx` for DOCX, raw UTF-8
  decode for TXT — both library imports are try/except-wrapped so the router
  degrades gracefully if a package is missing.
- Hard limits: 5MB max upload; under 20 extracted words is treated as a
  scanned/unparsable file (`ParseStatus.FAILED_SCANNED_OR_EMPTY`) and falls
  back to a generic interview instead of erroring.
- JD text is trimmed to Responsibilities/Requirements/Qualifications only
  (drops Benefits/Perks/About Us/Legal/Compensation via header matching),
  with a 600-word hard cap as fallback if no section headers are found.
- **Matching is not LLM-based** — it's a static ~30-term keyword list
  (`SKILL_KEYWORDS`) intersected between resume and JD text.
  `overlap_score = |intersection| / |jd_keywords|`, mismatch flagged below
  0.2. This is a coarse heuristic, not semantic matching — don't assume it
  catches paraphrased skills.
