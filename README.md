# SkillAlign — Intelligent Workforce Skill Alignment System

A working academic prototype built with React + TypeScript, FastAPI, SQLAlchemy and PostgreSQL. It supports a student demo workflow: career-role catalogue, skill assessments, transparent skill-gap scoring, learning resources/progress, CSV job ingestion, dictionary-baseline skill extraction, job-market analytics and a faculty summary.

> This is a development/academic prototype, not a production hiring or psychometric assessment product. It uses a small authored question bank and a rule/dictionary-based extractor. It does not claim a trained SkillSpan model or live ESCO API integration. Review the limitations below before describing results in a report.

## 1. Requirements
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ (the project was tested with PostgreSQL-compatible SQLAlchemy/Psycopg configuration)
- pgAdmin is optional; it is a database administration GUI.

## 2. Backend setup (Windows PowerShell)
Open a terminal in `backend`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

- `DATABASE_URL`: your local PostgreSQL password and database (the database must already exist).
  URL-encode reserved characters in the password (`@`, `:`, `/`, `#`, `%`).
- `SECRET_KEY`: a random value of at least 32 characters. Generate one with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Keep `.env` private and do not commit it.

### Create or upgrade the database schema (Alembic)
The schema is managed by Alembic migrations. **Back up an existing database first:**

```powershell
pg_dump -U postgres -F c -f skill_alignment_backup.dump skill_alignment_db
alembic upgrade head
```

`alembic upgrade head` creates a fresh schema, or safely adopts a version 1 database: it only adds
missing tables, columns and indexes, never drops data, and runs as one transaction on PostgreSQL.
The old shared demo account (`student@skillalign.local`) is deactivated; its records are kept.
The API refuses to start if the schema is not at the latest revision.

### Create the first administrator
No accounts are seeded. Create an administrator (the password is prompted for and hidden):

```powershell
python -m app.cli create-admin --email admin@your-college.edu --name "Your Name"
```

### Start the API

```powershell
uvicorn app.main:app --reload
```

On startup the application seeds the career roles, skill catalogue, question bank and free learning
resources (idempotently). API docs: http://127.0.0.1:8000/docs

Health checks:
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/health/db

## 3. Frontend setup
Open a second terminal in `frontend`:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://127.0.0.1:5173. The Vite dev server forwards `/api` requests to FastAPI
(`VITE_API_PROXY_TARGET`, default `http://127.0.0.1:8000`), so the browser talks to a single origin.
Leave `VITE_API_BASE_URL` empty: the secure refresh cookie only works on the same origin.

### Accounts and roles
- **Students** register themselves at `/register`.
- **Teachers/mentors** cannot self-register. An administrator invites them from *Mentor Invitations*;
  the invitee sets a password through the single-use link (emailed, or shown to the admin when SMTP is
  not configured).
- **Administrators** are created with the CLI above.
- Forgot password sends a 30-minute single-use link. Without SMTP settings, development mode prints the
  email to the API console.

## 4. Implemented modules
1. **Overview** — live counts, target role selector, weighted alignment and top skills from imported job postings.
2. **Skill assessment** — skill selection, MCQ delivery, answer submission, score, proficiency estimate and explanations. Results update the demo student's skill profile.
3. **Skill-gap analysis** — role skill requirements compared with latest assessed levels. Score is weighted and explainable; unassessed skills count as zero.
4. **Learning resources** — curated free official docs/courses/practice links with not-started, in-progress and completed tracking.
5. **Job market** — CSV import, required column validation, duplicate skip, simple text cleaning through field trimming, dictionary-based skill extraction and job/skill storage.
6. **Progress** — assessment history and tracked learning resource totals.
7. **Faculty insights** — aggregate local demo metrics.

## 5. CSV import format
Required columns: `title` (or `job_title` / `position`) and `description` (or `job_description` / `job_details`). Optional: `company`, `location`, `date` or `posted_date`.

A sample file is provided at `frontend/public/sample_jobs.csv`. In the Job Market page, download the template and upload it. The extractor currently recognizes a curated list of skill names and aliases. It is a baseline, not a production-grade NLP model.

## 6. API endpoints
All `/api/v1` endpoints except the public auth endpoints require `Authorization: Bearer <access token>`.
Permissions are enforced by the backend.

| Endpoint | Access |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `GET /auth/invitations/{token}`, `POST /auth/accept-invitation` | Public (rate-limited) |
| `GET /auth/me`, `POST /auth/change-password` | Any signed-in user |
| `GET /careers`, `/skills`, `/dashboard`, `/resources`, `/jobs`, `/analytics/skills`, `/assessments/skills`, `/assessments/questions/{skill_id}` | Any signed-in user |
| `POST /assessments/submit`, `GET /assessments/history`, `GET /gaps/{career_id}`, `GET/POST /progress` | Students (own data only) |
| `GET/PUT /students/me/profile`, `PUT /students/me/target-career`, `POST/GET/DELETE /students/me/photo` and `/resume`, `GET/PUT /students/me/self-skills`, `GET /students/me/dashboard` | Students (own profile only) |
| `GET /students/me/mentoring` | Students (own mentors and shared notes) |
| `GET/PUT /teachers/me/profile`, `POST/GET/DELETE /teachers/me/photo` | Teachers (own profile) |
| `GET /mentor/dashboard`, `GET /mentor/students`, `GET /mentor/students/{id}`, `POST /mentor/students/{id}/notes`, `DELETE /mentor/notes/{id}` | Teachers (assigned students only) and administrators |
| `POST /jobs/import-csv`, `GET /faculty/summary` | Teachers (scoped to assigned students) and administrators |
| `GET/POST /admin/invitations`, `POST /admin/invitations/{id}/revoke`, `GET /admin/users`, `GET/POST /admin/assignments`, `POST /admin/assignments/{id}/end` | Administrators |

## 7. Important limitations and next research steps
- **Authentication/authorization:** implemented in version 2 (Argon2id password hashing, 15-minute JWT access
  tokens kept in memory, rotating HttpOnly refresh cookies with reuse detection, role-based access checked
  against the database on every request, rate limiting, audit log). Rate limits are per process; use a
  shared store or proxy limits when running several workers. Mentors can access only students actively assigned to them
  by an administrator.
- **Assessment validity:** the included questions are a small demonstrative question bank. Add reviewed questions, broader difficulty coverage, question randomization, and validation with faculty/subject experts. A quiz score is not proof of employability.
- **NLP:** skill extraction is a transparent dictionary/regex baseline. To make a research-grade extractor, annotate a local India-focused test set, evaluate precision/recall/F1, and compare this baseline with a SkillSpan-trained token-classification model. SkillSpan is English-focused and is not included in this ZIP; obtain it from its official dataset page and follow its licence/terms.
- **ESCO:** the app has a skill catalogue that can be extended with ESCO identifiers/labels. It does not automatically download or synchronize ESCO. Download the official ESCO CSV and implement a reviewed concept/alias import before claiming ESCO integration.
- **Forecasting:** no demand forecasting model is implemented. Reliable dated job-posting history is required before forecasting.
- **Migrations:** SQLAlchemy `create_all` creates missing tables but does not migrate existing schema changes. Use Alembic for future schema changes.
- **Privacy:** use synthetic/demo records for testing. Add consent, retention, deletion, access controls and secure deployment configuration before collecting real student data.

## 8. Suggested validation checklist
- Verify `/health/db` returns `{"status":"ok","database":"connected"}`.
- Register a student, sign in, reload the page and confirm the session persists.
- Verify the seeded career roles and skills appear in the UI.
- Complete one assessment and confirm the result appears in Progress and changes the gap score.
- Import `sample_jobs.csv` and confirm job count/skill analytics update.
- Mark a resource completed and confirm Progress updates.
- Test invalid CSV, empty assessment answers and API-offline behavior.

## 9. Project architecture
`frontend/` contains the React app. `backend/app/` contains SQLAlchemy models, `routers/` (API endpoints), `services/` (business logic), authentication (`security.py`, `deps.py`) and configuration. `backend/alembic/` holds the database migrations and `backend/tests/` the automated tests (`TEST_DATABASE_URL=... pytest`; never point it at a real database). PostgreSQL stores users, skills, career roles, job postings, extracted job skills, questions, attempts, student skill levels, learning resources and learning progress.
