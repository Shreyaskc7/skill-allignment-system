"""Job-posting CSV import, job listing and skill-demand analytics."""

import csv
import io
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.deps import get_current_user, require_staff
from app.services.audit import audit
from app.services.skill_extraction import extract_skills, get_or_create_skill

router = APIRouter(tags=["jobs"])

TITLE_COLUMNS = ["title", "job_title", "position"]
DESCRIPTION_COLUMNS = ["description", "job_description", "job_details"]


@router.post("/jobs/import-csv")
async def import_jobs(
    request: Request,
    file: UploadFile = File(...),
    user: models.User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a CSV file")
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    fields = {f.lower().strip(): f for f in (reader.fieldnames or [])}
    title_col = next((fields[x] for x in TITLE_COLUMNS if x in fields), None)
    desc_col = next((fields[x] for x in DESCRIPTION_COLUMNS if x in fields), None)
    if not title_col or not desc_col:
        raise HTTPException(400, "CSV must contain title/job_title and description/job_description columns")

    count = 0
    skipped = 0
    found = Counter()
    for row in reader:
        title = (row.get(title_col) or "").strip()
        desc = (row.get(desc_col) or "").strip()
        if not title or not desc:
            skipped += 1
            continue
        company = (row.get(fields.get("company", "")) or "").strip() or None
        location = (row.get(fields.get("location", "")) or "").strip() or None
        dupe = db.scalar(
            select(models.JobPosting).where(models.JobPosting.title == title, models.JobPosting.description == desc)
        )
        if dupe:
            skipped += 1
            continue
        job = models.JobPosting(
            title=title[:200],
            company=company,
            location=location,
            description=desc,
            source=file.filename,
            posted_date=(row.get(fields.get("date", "")) or row.get(fields.get("posted_date", "")) or None),
        )
        db.add(job)
        db.flush()
        for name in extract_skills(desc + " " + title):
            sk = get_or_create_skill(db, name)
            db.add(models.JobSkill(job_id=job.id, skill_id=sk.id))
            found[name] += 1
        count += 1
    audit(db, "jobs.csv_import", user_id=user.id, details={"file": file.filename, "imported": count, "skipped": skipped}, request=request)
    db.commit()
    return {
        "imported": count,
        "skipped": skipped,
        "skills_found": dict(found),
        "message": "CSV imported and skill extraction completed using the built-in dictionary baseline.",
    }


@router.get("/jobs", dependencies=[Depends(get_current_user)])
def jobs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.JobPosting)
        .options(selectinload(models.JobPosting.skills).selectinload(models.JobSkill.skill))
        .order_by(models.JobPosting.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "source": j.source,
            "skills": [x.skill.name for x in j.skills],
        }
        for j in rows
    ]


@router.get("/analytics/skills", dependencies=[Depends(get_current_user)])
def analytics(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Skill.name, func.count(models.JobSkill.id))
        .join(models.JobSkill, models.Skill.id == models.JobSkill.skill_id)
        .group_by(models.Skill.id)
        .order_by(func.count(models.JobSkill.id).desc())
        .limit(20)
        .all()
    )
    return [{"skill": n, "postings": c} for n, c in rows]
