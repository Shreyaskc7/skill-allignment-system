"""Aggregate metrics. Not access-controlled yet (Phase 5 restricts this)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db

router = APIRouter(prefix="/faculty", tags=["faculty"])


@router.get("/summary")
def faculty_summary(db: Session = Depends(get_db)):
    avg = db.scalar(select(func.avg(models.AssessmentAttempt.score_percent)))
    return {
        "students": db.scalar(
            select(func.count(models.User.id)).where(models.User.role == models.UserRole.student)
        )
        or 0,
        "job_postings": db.scalar(select(func.count(models.JobPosting.id))) or 0,
        "assessments": db.scalar(select(func.count(models.AssessmentAttempt.id))) or 0,
        "skills_catalogued": db.scalar(select(func.count(models.Skill.id))) or 0,
        "average_assessment_score": round(avg or 0, 1),
    }
