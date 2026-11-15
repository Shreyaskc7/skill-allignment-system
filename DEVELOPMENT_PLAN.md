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

## Phase 3: Database migrations, authentication and frontend foundation ✅ done
**Migrations (Alembic)**
- `0001` v1 baseline is *adoptive*: on an existing version 1 database it adds only missing tables, columns and indexes (back-filling model defaults before NOT NULL), never drops anything, and runs in one PostgreSQL transaction. `0002` adds `users.last_login_at`, `password_reset_tokens` and `teacher_invitations`. It also replaces the faulty `UNIQUE(student_id, teacher_id, is_active)` with a partial unique index on active rows, and deactivates the v1 shared demo account, keeping its records.
- The API refuses to start on an out-of-date schema. `CREATE_TABLES_ON_START` is deprecated and ignored; `AUTO_MIGRATE` is opt-in. `scripts/migrate.py` is deprecated.
- Tested on a fresh DB, a full v1 `create_all` DB with data, and an older partial v1 schema with rows, on PostgreSQL 18 and SQLite. CI runs `alembic upgrade head` and `alembic check` (no model/migration drift).

**Authentication and authorization**
- Student self-registration (terms consent, password policy, normalised email, optional phone, profile row); login; logout; `/me`; change password; forgot/reset password (30-minute single-use links, no account enumeration); admin-issued single-use teacher invitations; `python -m app.cli create-admin`.
- Argon2id hashing (`argon2-cffi`, replacing unmaintained passlib). 15-minute JWT access tokens are held only in memory. Rotating opaque refresh tokens are stored as SHA-256 hashes in an HttpOnly, SameSite=Strict cookie scoped to `/api/v1/auth`. Reuse of an old token revokes all of that user's sessions, with a 15-second grace window so two tabs refreshing together do not log the user out.
- Every endpoint is protected. Roles are re-read from the database on each request, so a deactivation or role change takes effect immediately. Student data endpoints are scoped to the signed-in student; a verified v1 issue was that `/assessments/history` returned everyone's attempts. Job import and faculty summary are staff-only; invitations are admin-only.
- Login/register/reset rate limiting (in-process); audit log for auth and admin events; `SECRET_KEY` required in production (startup fails otherwise); `COOKIE_SECURE` enforced in production; SMTP optional (development prints emails to the console).

**Frontend foundation**
- `react-router-dom` routes with protected and role routes. Auth context restores the session on reload from the refresh cookie. The API client does a single-flight silent refresh. The Vite proxy gives a same-origin `/api`.
- Screens: landing, register, login, forgot password, reset password, accept invitation, admin mentor invitations. The sidebar and home page depend on the role.
- Shared UI: form fields with inline validation, password visibility toggle, alerts, toasts, confirm dialog, loading screen, error boundary, table styles. Auth pages verified at 375 px width.

**Verification:** 63 backend tests pass on PostgreSQL 18 and SQLite (19 run without any database). Browser walkthrough covered: student register → login → reload persistence → assessment → gaps (23%, matches hand calculation) → progress; admin invite → mentor accept → mentor login → CSV import; forgot/reset password; role redirects; no console errors.

**Found and fixed during the phase:** CLI crashed after creating an admin (detached session); CLI accepted emails the login form rejects; role-guarded routes lost the layout data (blank page), now fixed and protected by an error boundary; refresh-race handling.

**Deferred:** account/password-change screen (API exists) → Phase 4 profile; mentor scoping → Phase 5.

## Phase 4: Student profile and dashboard ✅ done
- Migration `0003`: `student_profiles.target_career_id`, plus a `student_self_skills` table. Self-reported levels are stored apart from assessed `student_skills`, so they never count as proficiency.
- `/api/v1/students/me/*` (student-only, always the signed-in student):
  - `GET/PUT profile` (personal, academic and career fields with validation; completion % listing what is missing)
  - `PUT target-career`
  - `POST/GET/DELETE photo|resume`
  - `GET/PUT self-skills`
  - `GET dashboard`
- Uploads: content checked by magic bytes (PNG/JPEG/WebP ≤ 2 MB, PDF ≤ 5 MB), stored under a random name in `backend/uploads/` (git-ignored, outside the web root), served only to their owner with `nosniff` and `no-store`. Path traversal in stored keys is refused, and replaced or deleted files are removed from disk.
- Dashboard from real records: target-career alignment (same weighted formula as Skill Gaps), prioritised missing skills, assessed skills, assessment count/average/best, learning progress, recommended resources for gap skills (excluding completed ones), and recent activity. Matching jobs show "available in a later release" (Phase 8) rather than fabricated data.
- Frontend: dashboard (target career chosen and saved from the hero), My Profile (sectioned form, inline validation, photo and resume, self-skill editor), Account (change password, available to all roles).
- Tests: 26 new (89 total) on PostgreSQL 18 and SQLite: validation, uploads with disguised and oversized files, traversal, self-skills not counted (alignment stays 0), dashboard alignment = Skill Gaps value (13% hand-calculated), student-to-student isolation, staff/anonymous rejection.
- Browser: register → dashboard → choose career → profile to 100% (real PNG upload; disguised file rejected) → self-skill added, alignment unchanged → password change (old rejected, session kept). No overflow at 375 px; no console errors.

## Phase 5: Teacher/mentor module and student assignment ✅ done
- Migration `0004`: mentoring notes can link a recommended learning resource and carry `visible_to_student` (concerns are always staff-only).
- **Scoping rule** (one service, `services/mentoring.py`, used by every mentor endpoint): administrators see all students; a teacher sees a student only while an active assignment exists; anything else returns 404 (no enumeration). Ending an assignment removes access immediately. `/faculty/summary` is scoped the same way.
- Teacher profile: `GET/PUT /teachers/me/profile` and a photo (same validated upload service as students).
- Admin: `GET /admin/users`, `GET/POST /admin/assignments`, `POST /admin/assignments/{id}/end` with a required reason. History is preserved (the Phase 3 partial index allows repeated inactive rows), and every change is audited.
- Mentor: `GET /mentor/dashboard` (students, participation, average score and alignment, completed resources, needs attention), `GET /mentor/students?search=`, `GET /mentor/students/{id}` (profile without personal data such as date of birth, gaps, assessment history, skill-level performance, learning, unverified self-reported skills, notes), `POST /mentor/students/{id}/notes`, `DELETE /mentor/notes/{id}` (own notes; admins any).
- "Needs attention" rules (documented, rule-based): no assessment, none in 14 days, average < 50%, alignment < 40%, no target career, or no tracked learning.
- Student: `GET /students/me/mentoring` shows active mentors and shared notes only; the dashboard has a Mentor feedback panel.
- Frontend: mentor dashboard (home for teachers and admins), Students (search and table), student detail with notes (feedback, recommendation with resource, private concern, delete with confirmation), teacher profile, admin Assignments (assign, end with reason, history toggle).
- Tests: 10 new (99 total) on PostgreSQL 18 and SQLite: cross-mentor isolation, search scoping, dashboard flags, detail contents (alignment 17% hand-checked), note visibility and ownership, end/reassign history, validation and permissions, audit.
- Browser: admin invites → mentor accepts → admin assigns via UI → mentor sees only the assigned student and adds three note types → unassigned student by URL shows "Student not found" → student sees shared notes only → admin ends assignment with a reason → mentor loses access. No console errors.
- **Deferred:** topic-wise performance needs per-question attempt records (Phase 6); skill-level performance is shown meanwhile.

## Phase 6: Assessment engine and question bank ✅ done
**Question bank:** 572 MCQs in `backend/app/question_bank/*.json` covering all 26 skills (22 each: 8 beginner, 8 intermediate, 6 advanced) with topic/subtopic and explanations. Correct letters are balanced across A–D, there are no duplicates, and all 17 version 1 questions are preserved verbatim. Soft skills use workplace scenarios.
- Loaded idempotently at startup with a stable `bank_key`. Staff edits and deactivations are never overwritten, and v1 rows are adopted rather than duplicated.
- Verified: an automated audit (counts, balance, duplicates, v1 preservation); JavaScript outputs run with Node by the authoring agent; the unverified pandas/NumPy outputs re-run and confirmed.
- **Needs review (honest limitation):** the correct option is the uniquely longest in 46% of questions (≈25% by chance), so test-wise guessing is easier than it should be. Questions were AI-assisted; faculty should review them, rewriting distractors to similar lengths, before using them for academic evaluation. Power BI/Tableau answers follow vendor behaviour from memory and were spot-checked, not exhaustively verified.

**Attempt engine (verified v1 bug fixed):** v1 scored every question of a skill rather than the ones delivered.
- Migration `0005`: attempt `status` (in_progress/submitted/expired/abandoned), difficulty, level, expiry and submit time; per-question snapshots (text, options, key, explanation, difficulty, topic, position). The question link is now ON DELETE SET NULL, because previously deleting a question would cascade-delete students' answer history. Student skills record `last_assessed_at` and `evidence_attempt_id`. v1 attempts become `submitted`.
- `POST /assessments/attempts`: server-side cryptographically random selection with a difficulty filter or a balanced mix, 5–30 questions, optional timer (90 s per question). No answer keys are sent. An unfinished attempt is resumed, not re-rolled (explicit restart abandons it).
- `POST /assessments/attempts/{id}/submit`: owner only (404 otherwise), once (409), within time limit + 30 s grace (else expired, unscored), delivered ids only, no duplicates, options A–D. Unanswered = incorrect. The skill level is updated only on submit.
- `GET /assessments/attempts/{id}`: in-progress view or results with difficulty-wise and topic-wise breakdowns and a full review. `GET /assessments/history`. Only submitted attempts count anywhere (dashboard, mentor, faculty, progress).
- Removed the v1 endpoints `GET /assessments/questions/{skill_id}` and `POST /assessments/submit`.
- **Documented correction:** the level mapping changed from v1 `round(score/20)` (half-to-even; 90% → 4 like 70%; 0% → 1) to equal bands 0–19 → 1, 20–39 → 2, 40–59 → 3, 60–79 → 4, 80–100 → 5. Stored levels are not recomputed. The weighted alignment formula is unchanged.

**Question management** (`/question-bank/questions`, teachers and admins): list with skill/difficulty/status/search filters and pagination, create, edit, enable/disable (no hard delete), validation (distinct options, case-sensitive; duplicate text per skill → 409), audited.

**Frontend:** setup screen (skill, count, difficulty, timer, instructions), one-question-at-a-time runner (previous/next, navigation grid with answered markers, progress, countdown with auto-submit, answers kept in the tab across reloads, confirmation naming unanswered questions), results page (score, level with bands, breakdowns, review with filter), history linked to results, staff Question Bank page.

**Tests:** 126 on PostgreSQL 18 and SQLite (23 new). They cover bank validity and idempotency, adoption of v1 questions, hidden answer keys, resume/restart, difficulty balance, every submission rejection, unanswered scoring, the time limit, results breakdowns, history surviving question edits, deactivated questions never delivered, and management permissions.
**Browser:** a 10-question mixed attempt with a reload mid-attempt (same questions and answers restored), submission with 6 unanswered, results and review, timed attempt countdown, 375 px layout, admin question edit/disable. No console errors.

## Phase 7: Skill analytics, skill gaps and career recommendations ✅ done
- **Alignment formula unchanged** (version 1 weighted formula in `services/alignment.py`). `services/career.py` explains and ranks; it does not change the formula. Everything is rule-based, not ML.
- `GET /gaps/{career_id}` (backward compatible, adds fields):
  - per skill: status (meets / needs_improvement / critical = gap ≥ 2 and weight ≥ 4), assessed or not, last assessed date, evidence attempt id (links to its results), self-reported level (shown, never counted), and contribution vs maximum in score points (they add up to the score)
  - a summary of counts, the formula text, and next steps: assess unassessed gaps first, then the first not-yet-completed resource for assessed gaps
- `GET /careers/recommendations`: all active roles ranked by alignment. Stated interests (profile career interests/target roles matched against role name, description and skills) only break ties and appear as reasons. Each role lists matching skills, skills to improve, unassessed skills, requirements and reasons; the target career is marked. The response states that scores are guidance, not hiring predictions.
- Frontend:
  - Skill Gaps page: summary tiles, "How is this calculated?" with the formula, contribution bars, status badges, evidence links, next steps.
  - New Careers page: ranked cards with reasons, set as target, gap details, side-by-side comparison of 2–3 roles.
- Tests: 8 new (134 total) on PostgreSQL 18 and SQLite. Hand-calculated: Python Backend 36% (8/22) with contributions summing to the score; Frontend 73% (16.75/23). They also cover status rules, next steps, self-reported exclusion, evidence links, ranking, interest tie-break without score change, and permissions.
- Browser: a real student took HTML and CSS assessments; Careers ranked Frontend Developer first at 22% (HTML 4 + CSS 1 = 5/23, hand-checked) with an interest reason; comparison, set as target, and gap details with formula and next steps all checked. No console errors.
- **Randomness check:** a student answering "B" to every HTML question scored 60%. 20,000 simulated draws confirmed selection is unbiased (observed 0.40% vs 0.28% theoretical); it was a rare outcome. Short 10-question attempts can be inflated by guessing, so 15–20 questions are recommended for any graded use.
- Note for Phase 9: only 9 skills have learning resources yet, so some next steps say "reassess" instead of naming a resource.

## Phase 8: Job market, extraction and student-to-job matching ✅ done
- Migration `0006`:
  - jobs gain `posted_on` (parsed date; raw text kept and back-filled), experience range, `is_active`, `dedupe_hash` and `created_by`
  - job skills gain `is_required` and `source` (extracted or manual)
  - new `skill_aliases` table, seeded idempotently
- **Extractor** (`services/skill_extraction.py`, rule-based, not ML, behind a `SkillExtractor` interface so a trained model can replace it): catalogue names plus ~60 aliases from the database, longest match first, negation ("no Java needed"), the verb sense of "excel in/at", and required vs optional from cues such as "nice to have", "preferred", "a plus" and "bonus".
- **Evaluation** (`scripts/evaluate_extractor.py`, `data/`): two hand-labelled SYNTHETIC sets, not real postings.

  | Set | Extractor | Precision | Recall | F1 |
  |---|---|---|---|---|
  | Development (30, written by the developer alongside the rules; overfit by design) | v1 baseline | 0.964 | 0.870 | 0.915 |
  | | current | 1.000 | 1.000 | 1.000 |
  | **Blind held-out** (40, written by an independent author who never saw the extractor) | v1 baseline | 0.851 | 0.829 | 0.840 |
  | | **current** | **0.922** | **0.915** | **0.918** |

  Required-vs-optional accuracy on the held-out set is 0.935. The held-out set was **not** used to tune rules. Remaining error types: "react"/"java" in other senses, "placement statistics", "X not required" negations, and soft-skill phrasings missing from the dictionary. CI fails if held-out F1 drops below 0.90.
- **Matching** (`services/jobs.py`, documented in the UI): a skill counts when the assessed level is ≥ 3/5 (self-reported never counts); match % = matched required ÷ required; optional skills are shown separately and never lower the score; no recognised skills → no score (not 0 or 100); "a high match does not guarantee selection".
- API:
  - `GET /jobs` (search by title/company, location, skill, minimum match, sort by relevance or date, pagination; inactive hidden from students)
  - `GET /jobs/{id}` (description, per-skill your-level vs needed, rule)
  - staff `POST /jobs` (manual entry, explicit skills or extraction, validation, 409 on duplicates) and `PUT /jobs/{id}`
  - CSV import: limits of 2 MB / 2000 rows, extra columns (experience, salary, url, employment type, explicit `skills`), per-row errors and warnings, duplicate detection within the file and against the database, date parsing, audited
- Student dashboard shows the top 3 real matches.
- Frontend: Job Market (filters, match badges, colour-coded skill chips, pagination, staff import with row report and an Add job dialog) and Job detail (required and nice-to-have with your level, "Assess/Improve" links, safe external apply link).
- Tests: 20 new (154 total) on PostgreSQL 18 and SQLite (extractor rules, evaluation regression floor, import validation, limits, manual entry, match rule, no-skill jobs, filters/sort/pagination, inactive jobs, dashboard).
- Browser: admin imported the sample plus a file with a bad row (row error reported), added a manual job; a student with Python 4, SQL 3, Linux 2, Java 5 saw 100% / 50% / 33% (hand-checked), filters, detail, dashboard top matches. No console errors.
- **Not done (optional, needs your data):** ESCO mapping and a trained extractor. The `esco_identifier`/`esco_label` columns exist but are unused.

## Phase 9: Personalised learning paths and progress ✅ done
- **Resource catalogue:** `backend/app/learning_resources.json` has 81 free resources covering all 26 skills (at least 2 each, usually 3–4), of types documentation, course, tutorial, practice, project and book, at beginner/intermediate/advanced level. The 11 version 1 resources are kept under their original titles, so existing progress stays linked.
  - **Every URL was checked with a live HTTP request (status 200) on 2026-11-15.** Tableau's training page returned 403 to automated checks and was **left out** rather than shipped unverified. Estimated hours are omitted because they could not be verified.
  - Loaded idempotently (matched by skill + title; never edits or deletes rows).
- **Learning path** (`GET /learning/path`, defaults to the target career):
  - steps are the unmet skills in gap order (critical first)
  - resource difficulty follows the assessed level (unassessed or 1–2 → beginner, 3 → intermediate, 4–5 → advanced; closest first; completed ones skipped)
  - step status: not assessed / to do / in progress / ready to reassess; met skills are listed separately; the rules are returned and shown in the UI
- **Progress:**
  - `POST /progress/{id}` validates status and notes (≤ 2000 characters); `started_at` is set on first start, and `completed_at` is set once and kept when re-saved; resetting clears both
  - `GET /learning/history`
  - `GET /resources` gains skill, type, difficulty, status and search filters
- No migration was needed (the timestamps and notes columns already existed).
- Frontend: new Learning Path page (numbered steps, statuses, start/complete, assess/reassess links), Learning Resources (filters, notes dialog, difficulty badges), Progress (learning history with dates and notes).
- Tests: 10 new (164 total) on PostgreSQL 18 and SQLite. They cover catalogue validity and coverage, idempotent load, filters, the difficulty rule, path ordering and adaptation, status transitions, timestamps, notes, history, validation and permissions.
- Browser: a student targeting Data Analyst (SQL 5, Excel 3, Python 1) saw alignment 32% (hand-checked 9.33/29), SQL met, critical gaps first, intermediate Excel resources and beginner Python resources. Python went To do → In progress → Ready to reassess; notes and history checked. No console errors.

## Phase 10: Administration ✅ done
- New router `routers/admin_manage.py` (admin only, every mutation audited):
  - `GET /admin/stats`: active users by role, deactivated accounts, pending invitations, active assignments, submitted assessments (total and last 30 days), average score, catalogue sizes, active jobs, sign-ins in the last 30 days.
  - `GET /admin/accounts` (filters, search, pagination) and `PATCH /admin/accounts/{id}` (activate/deactivate, change role, reason recorded).
    - **Safety rules:** an admin cannot deactivate or demote themselves; the last active admin is protected; deactivation revokes every refresh token (instant sign-out).
    - A role change ends active assignments that no longer fit (history kept) and creates the missing profile.
  - Skills: `POST/PUT /admin/skills` (unique names, ESCO fields optional).
  - Career roles: `GET/POST/PUT /admin/careers` with a full requirement editor (levels and weights 1–5, no duplicates) and active/hidden. **Hidden roles disappear from students' career lists and recommendations.** Requirement changes flow straight into alignment (tested 100% → 60%).
  - Learning resources: `POST/PUT/DELETE /admin/resources` (http(s) links only, known types and levels, unique title per skill; deletion refused when students have progress).
  - `GET /admin/audit`: filters by action prefix, user and entity, paginated, with actor email and IP.
- **Permission matrix test:** every `/admin` endpoint (19), read from the OpenAPI schema, is called as student (403), teacher (403) and anonymous (401). New admin endpoints are covered automatically.
- Frontend: Admin Dashboard (admin home: stats, shortcuts, recent activity), Users (filters, role select, activate/deactivate with a reason and confirmation; your own row is protected), Catalogue (career roles with requirement editor, skills, resources with delete protection), Audit Log (filters, pagination).
- Tests: 14 new (178 total) on PostgreSQL 18 and SQLite.
- Browser: admin home stats; created a career role with two requirements; deactivated a student with a reason (their login then returns 403); own row cannot be deactivated; the audit log shows every step, including a failed sign-in. No console errors.

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
