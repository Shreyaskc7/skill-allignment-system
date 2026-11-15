"""Explainable skill-gap analysis and career recommendations (students, own data only)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.deps import require_student
from app.services.career import gap_analysis, recommendations

router = APIRouter(tags=["skill gaps"])


@router.get("/gaps/{career_id}")
def gaps(career_id: int, user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    role = db.scalar(
        select(models.CareerRole)
        .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
        .where(models.CareerRole.id == career_id)
    )
    if not role:
        raise HTTPException(404, "Career not found")
    return gap_analysis(db, role, user.id)


@router.get("/careers/recommendations")
def career_recommendations(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    return recommendations(db, user)
