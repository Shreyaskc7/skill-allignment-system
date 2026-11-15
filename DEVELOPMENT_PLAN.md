# SkillAlign Version 2: Development Plan

Branch: `version-2` (created from `develop`). Original project preserved as tag `v1.0-baseline`.
Source requirements: the *Master Project Completion Prompt* (sections 1–21).
Way of working: one phase at a time, all work committed to `version-2`, CI green before a phase is marked done.

---

## 0. Verification of the master prompt against the actual codebase

The prompt was checked line by line against the code on `version-2`. It is broadly accurate. These points differ from what the code actually contains, or need a decision, and the plan below accounts for them.

### 0.1 Factual corrections

| # | Prompt says | Actual state | Impact on plan |
|---|-------------|--------------|----------------|
| 1 | Project contains `data/` | No `data/` directory exists. Sample data lives in `frontend/public/sample_jobs.csv`. | Phase 8 creates `data/` for sample/import datasets. |
| 2 | Lists `backend/app/main.py`, `models.py`, `schemas.py` … | Correct, but `schemas.py`, `security.py` and most of `models.py` (User auth fields, StudentProfile, TeacherProfile, assignments, mentoring notes, audit log, refresh tokens) are **already written but not used by any endpoint**. | Phases 3–5 wire up existing scaffolding instead of rewriting it. |
| 3 | Existing features 1–14 | All 14 exist, but in one 240-line `main.py` and one 31-line minified `App.tsx` with no router. | Phase 2 restructures into routers/services and pages without changing behaviour. |
| 4 | "Never hardcode a demo student as the active user" | 4 endpoints (assessment submit, gaps, progress read/write) plus the seed use `student@skillalign.local`; existing assessment/progress rows in your PostgreSQL belong to that user. | Phase 3 removes the hardcoding. Existing demo rows are **kept** (rule 3) and the demo user becomes an inactive legacy account. |
| 5 | Assessment must evaluate only delivered questions | **Verified bug:** `/assessments/submit` scores against *all* questions for the skill, not those delivered. | Fixed in Phase 6 (attempt records with delivered question IDs). |
| 6 | Correct answers not sent before submission | Already true: `/assessments/questions` omits `correct_option` (now covered by a test). | Preserve. |
| 7 | Keep historical attempts when question bank changes | `AssessmentAttemptQuestion` stores only `question_id`; editing a question silently rewrites history. | Phase 6 snapshots question text, options and correct answer per attempt. |
| 8 | Mentor assignment history and reassignment | **Verified schema bug:** `UniqueConstraint(student_id, teacher_id, is_active)` blocks a second *inactive* (historical) row for the same pair, so reassignment history breaks. | Phase 3 migration replaces it with a partial unique index `WHERE is_active`. |
| 9 | Skill: "last assessed date" and "assessment evidence" | `StudentSkill` has `level`, `source`, `updated_at` only. | Phase 7 adds `last_assessed_at` and `evidence_attempt_id`. |
| 10 | Jobs: experience requirements, required skills | `JobPosting` has no experience field. Skills are only extracted, not marked required/optional. | Phase 8 migration. |
| 11 | Docker Compose credentials must match docs | **Verified mismatch:** compose uses `skill_alignment` / `skill_user`; `.env.example` and README use `skill_alignment_db` / `postgres`. | Phase 2. |
| 12 | Alembic migrations | `alembic` is in requirements but there is no `alembic/` config. Schema is managed by `create_all` plus the custom `scripts/migrate.py`. | Phase 3 introduces Alembic with a baseline that can be safely **stamped** on your existing DB. |

### 0.2 Conflicts and decisions

| Topic | Decision |
|-------|----------|
| Rule 14 says "do not stop after a plan" | You asked for phase-by-phase delivery, which overrides it. This document is the plan; each phase is then fully implemented and tested. |
| "Create a backup / separate development copy" | Done with git: tag `v1.0-baseline` and branch `main` remain untouched. Your local PostgreSQL is never modified by tests; Phase 3 adds a `pg_dump` backup step before the first real migration. |
| Phase order: mentors (5) need admin-made assignments, but admin is Phase 10 | Phase 3 adds a CLI to create the first administrator. Phase 5 adds assignment **API** endpoints (admin-only). Phase 10 adds the full admin UI. |
| Section 14 (22 frontend screens) has no phase of its own | Frontend foundation (router, API client, auth context, layout, shared components) goes in Phase 3. Each later phase ships its own screens. |
| New technology (rule 13) | Proposed additions only: `react-router-dom` (needed for 22 screens and protected routes), `pytest`/`httpx` (tests). Charts use small in-house SVG/CSS components, not a chart library. Rate limiting uses an in-process limiter, not Redis. Anything else needs your approval first. |
| Question bank size | 26 skills × ≥20 = **≥520 MCQs**. Soft skills (Communication, Teamwork, Problem Solving) get scenario-based questions. AI-assisted questions must be reviewed by faculty before academic use; the plan includes an export for that review. |
| Forgot/reset password needs email | SMTP settings are optional. Without them, development mode logs the reset link to the server console. This is documented, not faked. |
| ESCO, ML skill extraction, demand forecasting (section 16) | **Optional**, and only if you supply the datasets (ESCO CSV, annotated job data, dated job history). The core app must not depend on them. Each is a stretch item in Phases 8 and 11, never claimed unless implemented and evaluated. |
| Final ZIP (section 19) | Produced in Phase 12 from the git tree (`git archive`), so `.env`, `.venv`, `node_modules` and caches can't leak. |
| Test database | Tests run **only** against `TEST_DATABASE_URL` (CI uses a disposable PostgreSQL container) and refuse to run otherwise. This is already enforced. |

### 0.3 Environment notes
- `backend/.venv` was copied from another PC and does not run here. Recreate it with `py -m venv .venv`. Local Python is 3.15; CI tests 3.11 and 3.12.
- CI (`.github/workflows/ci.yml`) runs backend tests on PostgreSQL 16 and the frontend type-check and build on every push to `main`, `develop`, `version-2` and `phase-*`, and on every PR.

---

## Phase 1: Audit and backup ✅ done
- Full audit of every source and config file (findings in §0 and in the Phase 2 list).
- Repository created on `Shreyaskc7/skill-allignment-system`; original tagged `v1.0-baseline`.
- Hardcoded DB password removed from `scripts/migrate.py` before the first commit.
- CI workflow and first smoke-test suite (7 tests) added.

## Phase 2: Stabilise the current application ✅ done
- Bug fixes (commit `0206824`): missing `Award` import (Faculty page crash), demo-user seed failing on a fresh DB, Argon2 cost misconfiguration (600000 "rounds"), missing `email-validator`, two TypeScript build errors.
- Backend split: `main.py` (240 lines) became `routers/` (health, catalog, assessments, gaps, learning, jobs, faculty), `services/` (alignment, skill_extraction, current_user), `seed.py` and `seed_data.py`. The weighted alignment formula was moved verbatim into `services/alignment.py`. N+1 queries were removed from history, progress, resources, jobs and gaps.
- **Behaviour check:** a scripted 51-call API scenario gave identical responses before and after the split. The only intended change is the new `status` field on `/resources`.
- Frontend split: `App.tsx` (31 dense lines) became `api/client.ts`, `types.ts` (typed API responses, no `any`), `hooks/` (data loading, assessment state), `components/` and 7 `pages/`. `styles.css` was formatted to readable form, with content verified identical (same build hash).
- Fixed: resource progress dropdown now shows the saved status.
- CORS origins configurable through `FRONTEND_ORIGINS` (defaults keep the previous ports).
- `docker-compose.yml` aligned with `.env.example` (`skill_alignment_db` / `postgres`); password read from a git-ignored root `.env`, never hardcoded; validated in CI.
- Documented, not changed: the level mapping uses Python's round-half-to-even (10%→1, 30%→2, 50%→2, 70%→4, 90%→4; 0%→1). Decision deferred to Phase 6, where attempts of 10+ questions make these cases common.
- Tests: 26 (18 unit tests for alignment, levels, extraction and CORS; 8 API tests). Browser walkthrough of all 7 pages, with no console or server errors.

## Phase 3: Database migrations, authentication and frontend foundation
- Alembic setup; baseline revision = current models. Procedure for your existing DB: `pg_dump` backup → run additive check → `alembic stamp`. Rehearsed on a restored copy, never on the live DB first.
- Migration: fix assignment unique constraint (§0.1 #8); refresh-token table in use.
- Auth API: register (student only), login, refresh (rotating, hashed refresh tokens), logout, `/me`, change password, forgot/reset password (signed, single-use, expiring token; SMTP optional).
- Account activation checks, login rate limiting, audit log entries for auth events.
- `get_current_user` and `require_role(...)` dependencies; remove every `student@skillalign.local` lookup; legacy demo user set inactive with data preserved.
- `create-admin` CLI for the first administrator; teacher accounts created only by admin invitation.
- Secrets (`SECRET_KEY`, `REFRESH_SECRET`) required from env, with startup failure in production if left at defaults.
- Frontend foundation: `react-router-dom`, typed API client with token refresh, auth context and persistence, protected and role routes, app layout and sidebar, shared UI (buttons, forms, tables, toasts, dialogs, loading/empty/error states).
- Screens: Landing, Register, Login, Forgot/Reset password.

**Exit tests:** register, login, invalid login, refresh, logout, reset, role guard, inactive account, migration upgrade on empty DB and stamp on existing-schema DB.

## Phase 4: Student profile and dashboard
- Student profile CRUD (`StudentProfile` already modelled): personal, academic and career fields; profile image and resume upload with type and size validation, stored outside the web root.
- Profile completion percentage; target career selection persisted per student.
- Self-reported skills stored separately (`source=self_reported`) and never counted as assessed proficiency.
- Student dashboard from real data: alignment, assessed and missing skills, assessment performance, learning progress, recommended resources, matching jobs (placeholder section until Phase 8, shown as "not available yet", not faked), recent activity.
- Object-level authorization: a student can only read or write their own records.

**Exit tests:** profile read/update, upload validation, cross-student access returns 403/404.

## Phase 5: Teacher/mentor module and student assignment
- Teacher profile CRUD (`TeacherProfile` already modelled).
- Admin-only assignment API: assign, reassign, remove, with reason, history and audit log.
- Mentor dashboard: assigned students, active count, assessment participation, average performance, gap and alignment summaries, learning progress, "needs attention" rules (documented thresholds).
- Student management: search, profile, assessment history, topic-wise performance, gaps, progress (read-only).
- Mentoring notes and feedback, and resource recommendations to a student.
- Mentors can only access assigned students, enforced in queries and not just the UI.

**Exit tests:** mentor sees assigned student only; access to an unassigned student is rejected; notes CRUD; assignment history preserved after reassignment.

## Phase 6: Assessment engine and question bank
- Question bank: ≥20 MCQs for each of the 26 skills, balanced beginner/intermediate/advanced, each with topic/subtopic, explanation and active flag. Authored as versioned seed files (`backend/app/seed/questions/*.json`), loaded idempotently, with duplicate detection.
- Attempt lifecycle: `POST /assessments/start` creates an attempt (status, started_at, optional time limit) with randomised delivered question IDs and difficulty filter or mixed difficulty.
- Submit validates: attempt owner, not already submitted, only delivered IDs, no duplicates, options A–D, time limit.
- Per-attempt snapshot of question text, options and correct answer, so history survives later edits.
- Results: score, per-question review with explanations, difficulty-wise and topic-wise breakdown; skill level updated only after a successful submit.
- UI: instructions, one-question-at-a-time view, previous/next, navigation panel, answered markers, progress, optional timer, confirm-submit dialog, results page, history.
- Question management (teacher/admin): create, edit, disable, filter, validation.

**Exit tests:** every rejection rule; scoring accuracy; answers never in start/delivery payloads; history unchanged after a question edit.

## Phase 7: Skill analytics, skill gaps and career recommendations
- `StudentSkill.last_assessed_at` and `evidence_attempt_id` (migration).
- Gap engine keeps the **existing weighted formula unchanged**: `Σ(min(level, required)/required × weight) / Σweight`. Each skill's contribution is now exposed; unassessed skills are shown as unassessed, not 0-proficient-but-proven.
- Categories: meets requirement / needs improvement / critical missing; recommended next steps.
- Career recommendations: rank roles by the same alignment score, with a **documented, rule-based** adjustment for interests and preferences. Shows matching, missing and to-improve skills and a learning path link, plus a side-by-side role comparison. Labelled rule-based, not ML, and never presented as a hiring probability.

**Exit tests:** alignment equals hand-calculated values for fixed fixtures; recommendation ordering; self-reported skills excluded from proficiency.

## Phase 8: Job market, extraction and student-to-job matching
- Migration: experience requirement, required vs optional skills, posting date as a date type (with safe conversion of existing string values).
- Manual job entry (teacher/admin); CSV import kept, with stronger validation, a per-row error report and duplicate detection.
- Extractor refactor: alias table in the DB, case-insensitive multi-word matching, normalisation, behind an `Extractor` interface so a trained model can plug in later. Precision/recall reported on a small **hand-labelled** sample set in `data/`.
- Job matching: match % = share of the job's required skills the student meets at the assessed level, with the formula shown in the UI. Lists matching, missing and additional skills.
- Job list with search (title, company), filters (location, skill, min match), sort (relevance, date), pagination; job detail page with gap info.
- *(Optional, needs your dataset)* ESCO concept mapping with source and licence recorded.

**Exit tests:** import validation and duplicates, extractor cases, match calculation, filters and pagination.

## Phase 9: Personalised learning paths and progress
- Resource model: type (documentation, video, tutorial, practice, project, certification), verified duration, free/paid. More curated resources for all 26 skills, linking only legitimate free or official sources.
- Recommendation engine: ordered by gap size × importance for the target career, filtered by current level and difficulty, excluding completed resources.
- Learning path generation per target career, adapted to assessed gaps.
- Progress: start, in progress, complete, notes, started/completed timestamps, history.

**Exit tests:** recommendations change after an assessment; progress transitions; history.

## Phase 10: Administration
- Admin dashboard with system statistics.
- Management UIs: users (activate/deactivate, roles), teacher invitations, assignments, skills, career roles and requirements, questions, resources, job postings.
- Audit log viewer; every admin mutation audited.
- Students and teachers blocked from all admin routes at the API level.

**Exit tests:** admin CRUD; non-admin 403 on every admin endpoint; audit rows written.

## Phase 11: Integration, security hardening and optimisation
- End-to-end API workflow test covering the 20-step journey in §17 of the prompt, run in CI against PostgreSQL.
- Browser flow check (Playwright, if approved) of the main student and mentor journeys.
- Security review: authorization matrix test (every endpoint × role), upload validation, CORS, safe error bodies, rate limits, secrets.
- Performance: N+1 removal (`selectinload`), indexes, pagination everywhere, transactions on multi-step writes.
- Responsive and accessibility pass on all screens.
- *(Optional, needs dated job history)* demand-forecasting baseline with evaluation, or documented as not feasible.

**Exit:** full test suite green in CI; build green; documented manual test record.

## Phase 12: Documentation, deployment and final package
- Backend and frontend Dockerfiles; compose with PostgreSQL, health checks, a persistent named volume (never recreated), and a migration step.
- `.env.example` files complete and matching the compose file.
- Docs: `README.md`, `PROJECT_ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `API_DOCUMENTATION.md`, `TESTING_GUIDE.md`, `DEPLOYMENT_GUIDE.md`, `PROJECT_STATUS.md`, describing only verified features.
- Fresh-machine setup test following the README.
- Final ZIP via `git archive`, so it excludes `.env`, `.venv`, `node_modules`, caches and DB files; tag `v2.0`.
- Honest completion report: completed, partial and not implemented (with reasons), test results, build results, security limitations, startup commands.

---

## Per-phase checklist (applied at the end of every phase)
1. Files created/modified listed in the phase commit message and in `PROJECT_STATUS.md`.
2. Migrations (if any) tested on an empty DB **and** on a copy of an existing-schema DB.
3. `pytest` (PostgreSQL) and `npm run build` pass locally and in CI, with real results reported.
4. Remaining issues recorded, nothing silently skipped.
5. Pushed to `version-2`; tagged `v2-phase-N`.

## Inputs needed from you along the way
| When | What |
|------|------|
| Phase 3 | Confirm a `pg_dump` backup of your local `skill_alignment_db` can be taken before the first real migration. |
| Phase 3 | SMTP details for password-reset emails (optional; console fallback otherwise). |
| Phase 6 | Faculty reviewer for the question bank (recommended for academic use). |
| Phase 8 | Real job-posting CSVs you are permitted to use; optional ESCO dataset. |
| Phase 11 | Approval to add Playwright for browser tests; optional dated job history for forecasting. |
