# SkillAlign — Intelligent Workforce Skill Alignment System

A working academic prototype built with React + TypeScript, FastAPI, SQLAlchemy and PostgreSQL. It supports a student demo workflow: career-role catalogue, skill assessments, transparent skill-gap scoring, learning resources/progress, CSV job ingestion, dictionary-baseline skill extraction, job-market analytics and a faculty summary.

> This is a development/academic prototype, not a production hiring or psychometric assessment product. It uses a local demo student profile, a small authored question bank and a rule/dictionary-based extractor. It does not claim a trained SkillSpan model or live ESCO API integration. Review the limitations below before describing results in a report.

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

Edit `backend/.env` and set the password for your local PostgreSQL `postgres` user. The database must already exist. For the database created during setup, use:

```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/skill_alignment_db
CREATE_TABLES_ON_START=true
```

If your password contains URL-reserved characters (`@`, `:`, `/`, `#`, `%`), URL-encode those characters. Keep `.env` private and do not commit it.

Start the API from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

On first start, SQLAlchemy creates any missing tables and the application seeds a demo student, career roles, skill catalogue, question bank and free learning resources. Existing starter tables are retained; `create_all` does not alter existing columns. API docs: http://127.0.0.1:8000/docs

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

Open the Vite URL, normally http://localhost:5173. The frontend expects the API at `http://127.0.0.1:8000`. Change `VITE_API_BASE_URL` in `frontend/.env` if needed.

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
- `GET /api/v1/dashboard`
- `GET /api/v1/careers`, `GET /api/v1/skills`
- `GET /api/v1/assessments/skills`
- `GET /api/v1/assessments/questions/{skill_id}`
- `POST /api/v1/assessments/submit`
- `GET /api/v1/assessments/history`
- `GET /api/v1/gaps/{career_id}`
- `GET /api/v1/resources`, `POST /api/v1/progress/{resource_id}`, `GET /api/v1/progress`
- `POST /api/v1/jobs/import-csv`, `GET /api/v1/jobs`
- `GET /api/v1/analytics/skills`, `GET /api/v1/faculty/summary`

## 7. Important limitations and next research steps
- **Authentication/authorization:** the UI currently uses a seeded demo student. Add real registration/login, password hashing, JWT/session security and role-based access before any multi-user deployment. Faculty summary is not access-controlled.
- **Assessment validity:** the included questions are a small demonstrative question bank. Add reviewed questions, broader difficulty coverage, question randomization, and validation with faculty/subject experts. A quiz score is not proof of employability.
- **NLP:** skill extraction is a transparent dictionary/regex baseline. To make a research-grade extractor, annotate a local India-focused test set, evaluate precision/recall/F1, and compare this baseline with a SkillSpan-trained token-classification model. SkillSpan is English-focused and is not included in this ZIP; obtain it from its official dataset page and follow its licence/terms.
- **ESCO:** the app has a skill catalogue that can be extended with ESCO identifiers/labels. It does not automatically download or synchronize ESCO. Download the official ESCO CSV and implement a reviewed concept/alias import before claiming ESCO integration.
- **Forecasting:** no demand forecasting model is implemented. Reliable dated job-posting history is required before forecasting.
- **Migrations:** SQLAlchemy `create_all` creates missing tables but does not migrate existing schema changes. Use Alembic for future schema changes.
- **Privacy:** use synthetic/demo records for testing. Add consent, retention, deletion, access controls and secure deployment configuration before collecting real student data.

## 8. Suggested validation checklist
- Verify `/health/db` returns `{"status":"ok","database":"connected"}`.
- Verify the seeded career roles and skills appear in the UI.
- Complete one assessment and confirm the result appears in Progress and changes the gap score.
- Import `sample_jobs.csv` and confirm job count/skill analytics update.
- Mark a resource completed and confirm Progress updates.
- Test invalid CSV, empty assessment answers and API-offline behavior.

## 9. Project architecture
`frontend/` contains the React app. `backend/app/` contains SQLAlchemy models, database setup, configuration and FastAPI endpoints. PostgreSQL stores users, skills, career roles, job postings, extracted job skills, questions, attempts, student skill levels, learning resources and learning progress.
