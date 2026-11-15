"""Job postings: validation, duplicate detection, skill linking and student-to-job matching.

Matching rule (rule-based, documented, shown in the UI):
* A student "has" a job skill when their ASSESSED level is >= MATCH_LEVEL (3 = working
  proficiency on the 1-5 scale). Self-reported levels never count.
* match % = required skills the student has / required skills of the job x 100.
* Optional ("nice to have") skills are listed separately and do not lower the score.
* A job with no recognised required skills has no match score (None), never a fake 0 or 100.
A high match does not mean the student will be selected.
"""

import hashlib
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.skill_extraction import extractor_from_db

MATCH_LEVEL = 3
MATCH_RULE = (f"A skill counts as matched when your assessed level is {MATCH_LEVEL}/5 or higher. "
              "Match % = matched required skills ÷ required skills. Optional skills do not lower the score.")
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y")


def parse_date(text: str | None) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime((text or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_experience(text: str | None) -> tuple[int | None, int | None]:
    """'0-2' -> (0, 2); '3+' / '3 years' -> (3, None); 'fresher' -> (0, 0)."""
    t = (text or "").strip().lower()
    if not t:
        return None, None
    if "fresher" in t:
        return 0, 0
    nums = [int(n) for n in re.findall(r"\d+", t)][:2]
    if len(nums) == 2:
        return min(nums), max(nums)
    if len(nums) == 1:
        return nums[0], None
    return None, None


def dedupe_hash(title: str, company: str | None, description: str) -> str:
    norm = lambda s: " ".join((s or "").lower().split())  # noqa: E731
    return hashlib.sha256(f"{norm(title)}|{norm(company)}|{norm(description)}".encode()).hexdigest()


def link_skills(db: Session, job: models.JobPosting, manual: list[tuple[int, bool]] | None = None) -> list[str]:
    """Attach skills: staff-chosen ones if given, otherwise extracted from title + description."""
    job.skills.clear()
    db.flush()
    if manual:
        for skill_id, required in manual:
            job.skills.append(models.JobSkill(skill_id=skill_id, is_required=required, source="manual"))
        db.flush()
        return [db.get(models.Skill, sid).name for sid, _ in manual]
    names = {s.name: s.id for s in db.scalars(select(models.Skill))}
    found = extractor_from_db(db).extract(f"{job.title}. {job.description}")
    for e in found:
        job.skills.append(models.JobSkill(skill_id=names[e.skill], is_required=e.required, source="extracted"))
    db.flush()
    return [e.skill for e in found]


def student_levels(db: Session, user_id: int) -> dict[int, int]:
    return dict(db.execute(select(models.StudentSkill.skill_id, models.StudentSkill.level)
                           .where(models.StudentSkill.user_id == user_id)).all())


def match(job: models.JobPosting, levels: dict[int, int] | None) -> dict:
    required = [js for js in job.skills if js.is_required]
    optional = [js for js in job.skills if not js.is_required]

    def item(js):
        lvl = (levels or {}).get(js.skill_id)
        return {"skill_id": js.skill_id, "skill": js.skill.name, "your_level": lvl,
                "has": lvl is not None and lvl >= MATCH_LEVEL}

    req_items = [item(js) for js in required]
    opt_items = [item(js) for js in optional]
    met = [i for i in req_items if i["has"]]
    return {
        "match_percent": None if levels is None or not req_items else round(len(met) / len(req_items) * 100),
        "matching_skills": [i["skill"] for i in met],
        "missing_skills": [i["skill"] for i in req_items if not i["has"]],
        "additional_skills": [i["skill"] for i in opt_items],
        "required": req_items,
        "optional": opt_items,
    }


def job_out(job: models.JobPosting, levels: dict[int, int] | None, detail: bool = False) -> dict:
    out = {
        "id": job.id, "title": job.title, "company": job.company, "location": job.location,
        "employment_type": job.employment_type, "experience_min_years": job.experience_min_years,
        "experience_max_years": job.experience_max_years, "salary_min": job.salary_min,
        "salary_max": job.salary_max, "salary_currency": job.salary_currency,
        "application_url": job.application_url, "posted_on": job.posted_on, "posted_date": job.posted_date,
        "source": job.source, "is_active": job.is_active, "created_at": job.created_at,
        "skills": [js.skill.name for js in job.skills],
        **match(job, levels),
    }
    if detail:
        out["description"] = job.description
        out["match_rule"] = MATCH_RULE
    return out
