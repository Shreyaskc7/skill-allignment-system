"""Aggregate metrics, scoped: administrators see all students, mentors only their assigned students."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_staff
from app.services.mentoring import visible_student_ids

router = APIRouter(prefix="/faculty", tags=["faculty"], dependencies=[Depends(require_staff)])


@router.get("/summary")
def faculty_summary(viewer: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    allowed = visible_student_ids(db, viewer)
    students = select(models.User.id).where(models.User.role == models.UserRole.student,
                                            models.User.is_active.is_(True))
    if allowed is not None:
        students = students.where(models.User.id.in_(allowed or [-1]))
    ids = list(db.scalars(students))
    in_scope = models.AssessmentAttempt.user_id.in_(ids or [-1])
    avg = db.scalar(select(func.avg(models.AssessmentAttempt.score_percent)).where(in_scope))
    return {
        "scope": "all students" if allowed is None else "assigned students",
        "students": len(ids),
        "job_postings": db.scalar(select(func.count(models.JobPosting.id))) or 0,
        "assessments": db.scalar(select(func.count(models.AssessmentAttempt.id)).where(in_scope)) or 0,
        "skills_catalogued": db.scalar(select(func.count(models.Skill.id))) or 0,
        "average_assessment_score": round(avg or 0, 1),
    }
