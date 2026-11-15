"""Job market: CSV import, manual entry, search/filter/sort, job detail with matching, analytics."""

import csv
import io
from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.deps import get_current_user, require_staff
from app.models import UserRole
from app.services import jobs as svc
from app.services.audit import audit

router = APIRouter(tags=["jobs"])

TITLE_COLUMNS = ["title", "job_title", "position"]
DESCRIPTION_COLUMNS = ["description", "job_description", "job_details"]
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 2000


class JobSkillIn(BaseModel):
    skill_id: int
    required: bool = True


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=160)
    description: str = Field(min_length=20, max_length=20000)
    employment_type: Literal["full-time", "part-time", "internship", "contract", "temporary"] | None = None
    experience_min_years: int | None = Field(None, ge=0, le=40)
    experience_max_years: int | None = Field(None, ge=0, le=40)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str | None = Field(None, max_length=10)
    application_url: str | None = Field(None, max_length=500, pattern=r"^https?://\S+$")
    posted_on: date | None = None
    skills: list[JobSkillIn] | None = Field(None, max_length=40, description="Leave empty to extract from the text")
    is_active: bool = True

    @field_validator("title", "company", "location", "description", "salary_currency", "application_url", mode="before")
    @classmethod
    def strip(cls, v):
        return (v.strip() or None) if isinstance(v, str) else v

    @model_validator(mode="after")
    def ranges(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot be greater than salary_max")
        if (self.experience_min_years is not None and self.experience_max_years is not None
                and self.experience_min_years > self.experience_max_years):
            raise ValueError("experience_min_years cannot be greater than experience_max_years")
        return self


def _levels_for(db: Session, user: models.User) -> dict[int, int] | None:
    return svc.student_levels(db, user.id) if user.role == UserRole.student else None


def _load(db: Session, job_id: int) -> models.JobPosting:
    job = db.scalar(select(models.JobPosting).options(selectinload(models.JobPosting.skills).selectinload(models.JobSkill.skill))
                    .where(models.JobPosting.id == job_id))
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def _manual_skills(db: Session, skills: list[JobSkillIn] | None) -> list[tuple[int, bool]] | None:
    if not skills:
        return None
    ids = [s.skill_id for s in skills]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Each skill can be listed only once")
    known = set(db.scalars(select(models.Skill.id).where(models.Skill.id.in_(ids))))
    if unknown := sorted(set(ids) - known):
        raise HTTPException(422, f"Unknown skill id(s): {unknown}")
    return [(s.skill_id, s.required) for s in skills]


# ------------------------------------------------------------------ list / detail

@router.get("/jobs")
def list_jobs(
    search: str | None = None, location: str | None = None, skill_id: int | None = None,
    min_match: int | None = Query(None, ge=0, le=100), sort: Literal["relevance", "date"] = "relevance",
    include_inactive: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = select(models.JobPosting).options(selectinload(models.JobPosting.skills).selectinload(models.JobSkill.skill))
    if not (include_inactive and user.role != UserRole.student):
        stmt = stmt.where(models.JobPosting.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(models.JobPosting.title.ilike(like), models.JobPosting.company.ilike(like)))
    if location:
        stmt = stmt.where(models.JobPosting.location.ilike(f"%{location.strip()}%"))
    if skill_id:
        stmt = stmt.where(models.JobPosting.skills.any(models.JobSkill.skill_id == skill_id))
    jobs = list(db.scalars(stmt))
    levels = _levels_for(db, user)
    items = [svc.job_out(j, levels) for j in jobs]
    if min_match is not None and levels is not None:
        items = [i for i in items if (i["match_percent"] or 0) >= min_match]

    def by_date(i):
        return (i["posted_on"] or date.min, i["created_at"])

    items.sort(key=by_date, reverse=True)  # newest first; stable for the relevance sort below
    if sort == "relevance" and levels is not None:
        items.sort(key=lambda i: -1 if i["match_percent"] is None else i["match_percent"], reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size, "match_rule": svc.MATCH_RULE}


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _load(db, job_id)
    if not job.is_active and user.role == UserRole.student:
        raise HTTPException(404, "Job not found")
    return svc.job_out(job, _levels_for(db, user), detail=True)


# ------------------------------------------------------------------ staff: manual entry and editing

@router.post("/jobs", status_code=201)
def create_job(body: JobIn, request: Request, user: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    h = svc.dedupe_hash(body.title, body.company, body.description)
    if db.scalar(select(models.JobPosting.id).where(models.JobPosting.dedupe_hash == h)):
        raise HTTPException(409, "This job posting already exists")
    manual = _manual_skills(db, body.skills)
    job = models.JobPosting(**body.model_dump(exclude={"skills"}), source="manual", dedupe_hash=h, created_by=user.id,
                            posted_date=body.posted_on.isoformat() if body.posted_on else None)
    db.add(job)
    db.flush()
    svc.link_skills(db, job, manual)
    audit(db, "jobs.created", user_id=user.id, entity_type="job", entity_id=job.id, request=request)
    db.commit()
    return svc.job_out(_load(db, job.id), None, detail=True)


@router.put("/jobs/{job_id}")
def update_job(job_id: int, body: JobIn, request: Request, user: models.User = Depends(require_staff),
               db: Session = Depends(get_db)):
    job = _load(db, job_id)
    manual = _manual_skills(db, body.skills)
    text_changed = (body.title, body.description) != (job.title, job.description)
    had_manual = any(js.source == "manual" for js in job.skills)
    for k, v in body.model_dump(exclude={"skills"}).items():
        setattr(job, k, v)
    job.posted_date = body.posted_on.isoformat() if body.posted_on else job.posted_date
    job.dedupe_hash = svc.dedupe_hash(job.title, job.company, job.description)
    if manual is not None or (text_changed and not had_manual):
        svc.link_skills(db, job, manual)
    audit(db, "jobs.updated", user_id=user.id, entity_type="job", entity_id=job.id, request=request)
    db.commit()
    return svc.job_out(_load(db, job.id), None, detail=True)


# ------------------------------------------------------------------ staff: CSV import

def _col(fields: dict[str, str], *names: str) -> str | None:
    return next((fields[n] for n in names if n in fields), None)


@router.post("/jobs/import-csv")
async def import_jobs(request: Request, file: UploadFile = File(...), user: models.User = Depends(require_staff),
                      db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Upload a CSV file")
    data = await file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV file is too large (maximum 2 MB)")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
    fields = {f.lower().strip(): f for f in (reader.fieldnames or []) if f}
    title_col, desc_col = _col(fields, *TITLE_COLUMNS), _col(fields, *DESCRIPTION_COLUMNS)
    if not title_col or not desc_col:
        raise HTTPException(400, "CSV must contain title/job_title and description/job_description columns")
    cols = {
        "company": _col(fields, "company", "company_name", "employer"),
        "location": _col(fields, "location", "city"),
        "date": _col(fields, "posted_date", "date", "posted_on"),
        "type": _col(fields, "employment_type", "job_type", "type"),
        "experience": _col(fields, "experience", "experience_years"),
        "salary_min": _col(fields, "salary_min"), "salary_max": _col(fields, "salary_max"),
        "currency": _col(fields, "salary_currency", "currency"),
        "url": _col(fields, "application_url", "url", "apply_url", "link"),
        "skills": _col(fields, "skills", "required_skills"),
    }
    skills_by_name = {s.name.lower(): s.id for s in db.scalars(select(models.Skill))}
    seen = set(db.scalars(select(models.JobPosting.dedupe_hash).where(models.JobPosting.dedupe_hash.isnot(None))))
    imported, skipped, errors, warnings, found = 0, 0, [], [], Counter()

    for n, row in enumerate(reader, start=2):  # row 1 is the header
        if n - 1 > MAX_CSV_ROWS:
            errors.append({"row": n, "message": f"Stopped: more than {MAX_CSV_ROWS} rows"})
            break
        get = lambda key: (row.get(cols[key]) or "").strip() if cols[key] else ""  # noqa: E731
        title, desc = (row.get(title_col) or "").strip(), (row.get(desc_col) or "").strip()
        problems = []
        if not title or not desc:
            problems.append("title and description are required")
        if len(title) > 200:
            problems.append("title is longer than 200 characters")
        url = get("url")
        if url and not url.lower().startswith(("http://", "https://")):
            problems.append("application_url must start with http:// or https://")
        salaries = {}
        for key in ("salary_min", "salary_max"):
            raw = get(key).replace(",", "")
            if raw:
                if not raw.isdigit():
                    problems.append(f"{key} must be a whole number")
                else:
                    salaries[key] = int(raw)
        if problems:
            skipped += 1
            errors.append({"row": n, "message": "; ".join(problems)})
            continue
        company = get("company") or None
        h = svc.dedupe_hash(title, company, desc)
        if h in seen:
            skipped += 1
            warnings.append({"row": n, "message": "duplicate of an existing posting; skipped"})
            continue
        seen.add(h)
        raw_date = get("date") or None
        posted_on = svc.parse_date(raw_date)
        if raw_date and posted_on is None:
            warnings.append({"row": n, "message": f"unrecognised date '{raw_date}' kept as text"})
        manual = []
        for name in filter(None, (x.strip() for x in get("skills").replace(";", ",").split(","))):
            if name.lower() in skills_by_name:
                manual.append((skills_by_name[name.lower()], True))
            else:
                warnings.append({"row": n, "message": f"unknown skill '{name}' ignored"})
        exp_min, exp_max = svc.parse_experience(get("experience"))
        job = models.JobPosting(
            title=title, company=company, location=get("location") or None, description=desc,
            source=(file.filename or "csv")[:100], posted_date=raw_date, posted_on=posted_on,
            employment_type=(get("type") or None), experience_min_years=exp_min, experience_max_years=exp_max,
            salary_min=salaries.get("salary_min"), salary_max=salaries.get("salary_max"),
            salary_currency=(get("currency") or None), application_url=url or None, dedupe_hash=h, created_by=user.id,
        )
        db.add(job)
        db.flush()
        for name in svc.link_skills(db, job, list(dict.fromkeys(manual)) or None):
            found[name] += 1
        imported += 1

    audit(db, "jobs.csv_import", user_id=user.id,
          details={"file": file.filename, "imported": imported, "skipped": skipped}, request=request)
    db.commit()
    return {
        "imported": imported, "skipped": skipped, "skills_found": dict(found), "errors": errors, "warnings": warnings,
        "message": "CSV imported. Skills were taken from the 'skills' column when present, otherwise extracted "
                   "from the text with the rule-based dictionary extractor.",
    }


# ------------------------------------------------------------------ analytics

@router.get("/analytics/skills", dependencies=[Depends(get_current_user)])
def analytics(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Skill.name, func.count(models.JobSkill.id))
        .join(models.JobSkill, models.Skill.id == models.JobSkill.skill_id)
        .join(models.JobPosting, models.JobPosting.id == models.JobSkill.job_id)
        .where(models.JobPosting.is_active.is_(True))
        .group_by(models.Skill.id, models.Skill.name)
        .order_by(func.count(models.JobSkill.id).desc(), models.Skill.name)
        .limit(20)
        .all()
    )
    return [{"skill": n, "postings": c} for n, c in rows]
