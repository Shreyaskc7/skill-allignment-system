from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.services.alignment import career_alignment
from app.services.current_user import get_demo_student

router = APIRouter(prefix="/gaps", tags=["skill gaps"])


@router.get("/{career_id}")
def gaps(career_id: int, db: Session = Depends(get_db)):
    role = db.scalar(
        select(models.CareerRole)
        .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
        .where(models.CareerRole.id == career_id)
    )
    if not role:
        raise HTTPException(404, "Career not found")
    user = get_demo_student(db)
    levels = dict(
        db.execute(
            select(models.StudentSkill.skill_id, models.StudentSkill.level).where(
                models.StudentSkill.user_id == user.id
            )
        ).all()
    )
    score, rows = career_alignment(role.skills, levels)
    return {"career": role.name, "alignment_score": score, "skills": rows}
