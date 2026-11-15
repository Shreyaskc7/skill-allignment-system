"""Career roles, skills and the overview dashboard counts."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db

router = APIRouter(tags=["catalog"])


@router.get("/careers")
def careers(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.CareerRole)
        .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
        .order_by(models.CareerRole.name)
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "skills": [
                {
                    "skill_id": x.skill_id,
                    "skill_name": x.skill.name,
                    "required_level": x.required_level,
                    "importance_weight": x.importance_weight,
                }
                for x in r.skills
            ],
        }
        for r in rows
    ]


@router.get("/skills")
def skills(db: Session = Depends(get_db)):
    return [
        {"id": s.id, "name": s.name, "category": s.category, "description": s.description}
        for s in db.scalars(select(models.Skill).order_by(models.Skill.name)).all()
    ]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    top = (
        db.query(models.Skill.name, func.count(models.JobSkill.id))
        .join(models.JobSkill, models.Skill.id == models.JobSkill.skill_id, isouter=True)
        .group_by(models.Skill.id)
        .order_by(func.count(models.JobSkill.id).desc())
        .limit(8)
        .all()
    )
    return {
        "job_count": db.scalar(select(func.count(models.JobPosting.id))) or 0,
        "skill_count": db.scalar(select(func.count(models.Skill.id))) or 0,
        "assessment_count": db.scalar(select(func.count(models.AssessmentAttempt.id))) or 0,
        "resource_count": db.scalar(select(func.count(models.LearningResource.id))) or 0,
        "top_skills": [{"name": n, "count": c} for n, c in top],
    }
