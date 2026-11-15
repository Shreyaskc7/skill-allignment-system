"""Learning resources, learning path, progress tracking and learning history."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user, require_student
from app.security import utcnow
from app.services import learning as svc
from app.services.assessment import submitted_only

router = APIRouter(tags=["learning"])


class ProgressIn(BaseModel):
    status: Literal["not_started", "in_progress", "completed"] = "in_progress"
    notes: str | None = Field(None, max_length=2000)


@router.get("/resources")
def resources(
    skill_id: int | None = None, type: str | None = None, difficulty: str | None = None,
    status: Literal["not_started", "in_progress", "completed"] | None = None, search: str | None = None,
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = (select(models.LearningResource, models.Skill.name)
            .join(models.Skill, models.Skill.id == models.LearningResource.skill_id)
            .order_by(models.Skill.name, models.LearningResource.difficulty, models.LearningResource.title))
    if skill_id:
        stmt = stmt.where(models.LearningResource.skill_id == skill_id)
    if type:
        stmt = stmt.where(models.LearningResource.resource_type == type)
    if difficulty:
        stmt = stmt.where(models.LearningResource.difficulty == difficulty)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(models.LearningResource.title.ilike(like) | models.LearningResource.provider.ilike(like))
    progress = svc.progress_by_resource(db, user.id)
    rows = [svc.resource_out(r, name, progress.get(r.id)) for r, name in db.execute(stmt).all()]
    return [r for r in rows if status is None or r["status"] == status]


@router.post("/progress/{resource_id}")
def update_progress(resource_id: int, body: ProgressIn, user: models.User = Depends(require_student),
                    db: Session = Depends(get_db)):
    if db.get(models.LearningResource, resource_id) is None:
        raise HTTPException(404, "Resource not found")
    row = db.scalar(select(models.LearningProgress).where(
        models.LearningProgress.user_id == user.id, models.LearningProgress.resource_id == resource_id))
    if row is None:
        row = models.LearningProgress(user_id=user.id, resource_id=resource_id, notes="", status="not_started")
        db.add(row)
    now = utcnow()
    if body.status == "not_started":
        row.started_at = row.completed_at = None
    else:
        row.started_at = row.started_at or now
        if body.status == "completed":
            row.completed_at = row.completed_at if row.status == "completed" else now
        else:
            row.completed_at = None
    row.status = body.status
    if body.notes is not None:
        row.notes = body.notes.strip()
    db.commit()
    return {"status": row.status, "resource_id": resource_id, "notes": row.notes,
            "started_at": row.started_at, "completed_at": row.completed_at}


@router.get("/progress")
def progress(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    attempts = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == user.id, submitted_only())
        .order_by(models.AssessmentAttempt.created_at)
    ).all()
    records = db.scalars(select(models.LearningProgress).where(models.LearningProgress.user_id == user.id)).all()
    return {
        "attempts": [
            {"skill": name, "score": a.score_percent, "date": a.created_at.isoformat() if a.created_at else None}
            for a, name in attempts
        ],
        "resources": {
            "completed": sum(x.status == "completed" for x in records),
            "in_progress": sum(x.status == "in_progress" for x in records),
            "total_tracked": len(records),
        },
    }


@router.get("/learning/history")
def history(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.LearningProgress, models.LearningResource, models.Skill.name)
        .join(models.LearningResource, models.LearningResource.id == models.LearningProgress.resource_id)
        .join(models.Skill, models.Skill.id == models.LearningResource.skill_id)
        .where(models.LearningProgress.user_id == user.id, models.LearningProgress.status != "not_started")
        .order_by(models.LearningProgress.updated_at.desc(), models.LearningProgress.id.desc())
    ).all()
    return [svc.resource_out(r, name, p) | {"updated_at": p.updated_at} for p, r, name in rows]


@router.get("/learning/path")
def learning_path(career_id: int | None = None, user: models.User = Depends(require_student),
                  db: Session = Depends(get_db)):
    if career_id is None:
        profile = db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == user.id))
        career_id = profile.target_career_id if profile else None
        if career_id is None:
            raise HTTPException(409, "Choose a target career first (Dashboard or Careers page).")
    career = svc.load_career(db, career_id)
    if career is None:
        raise HTTPException(404, "Career not found")
    return svc.learning_path(db, user, career)
