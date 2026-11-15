"""Learning resources and learning progress."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user, require_student

router = APIRouter(tags=["learning"])

PROGRESS_STATUSES = ["not_started", "in_progress", "completed"]


@router.get("/resources")
def resources(skill_id: int | None = None, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = (
        select(models.LearningResource, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.LearningResource.skill_id)
        .order_by(models.LearningResource.title)
    )
    if skill_id:
        stmt = stmt.where(models.LearningResource.skill_id == skill_id)
    statuses = dict(
        db.execute(
            select(models.LearningProgress.resource_id, models.LearningProgress.status).where(
                models.LearningProgress.user_id == user.id
            )
        ).all()
    )
    return [
        {
            "id": r.id,
            "skill_id": r.skill_id,
            "skill": skill_name,
            "title": r.title,
            "provider": r.provider,
            "url": r.url,
            "type": r.resource_type,
            "difficulty": r.difficulty,
            "description": r.description,
            "is_free": r.is_free,
            "status": statuses.get(r.id, "not_started"),
        }
        for r, skill_name in db.execute(stmt).all()
    ]


@router.post("/progress/{resource_id}")
def update_progress(
    resource_id: int, payload: dict, user: models.User = Depends(require_student), db: Session = Depends(get_db)
):
    r = db.get(models.LearningResource, resource_id)
    if not r:
        raise HTTPException(404, "Resource not found")
    row = db.scalar(
        select(models.LearningProgress).where(
            models.LearningProgress.user_id == user.id, models.LearningProgress.resource_id == resource_id
        )
    )
    if not row:
        row = models.LearningProgress(user_id=user.id, resource_id=resource_id)
        db.add(row)
    status = payload.get("status", "in_progress")
    if status not in PROGRESS_STATUSES:
        raise HTTPException(400, "Invalid status")
    row.status = status
    row.notes = payload.get("notes", "")
    db.commit()
    return {"status": row.status, "resource_id": resource_id}


@router.get("/progress")
def progress(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    attempts = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == user.id)
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
