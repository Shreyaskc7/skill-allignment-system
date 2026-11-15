"""Mentor scoping, per-student summaries and "needs attention" rules.

Access rule (enforced here, used by every mentor endpoint):
  * administrators may view any student;
  * a teacher may view a student only while an ACTIVE assignment links them;
  * anything else is reported as "not found" (no enumeration of other students).
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.models import UserRole
from app.security import utcnow
from app.services.alignment import career_alignment

# "Needs attention" thresholds (documented, rule-based).
INACTIVE_DAYS = 14
LOW_AVERAGE = 50.0
LOW_ALIGNMENT = 40


def _aware(dt):
    from datetime import timezone

    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def assigned_student_ids(db: Session, teacher_id: int) -> list[int]:
    return list(db.scalars(
        select(models.StudentTeacherAssignment.student_id).where(
            models.StudentTeacherAssignment.teacher_id == teacher_id,
            models.StudentTeacherAssignment.is_active.is_(True),
        )
    ))


def visible_student_ids(db: Session, viewer: models.User) -> list[int] | None:
    """None means 'all students' (administrators)."""
    return None if viewer.role == UserRole.admin else assigned_student_ids(db, viewer.id)


def get_viewable_student(db: Session, viewer: models.User, student_id: int) -> models.User:
    student = db.get(models.User, student_id)
    allowed = visible_student_ids(db, viewer)
    if student is None or student.role != UserRole.student or (allowed is not None and student_id not in allowed):
        raise HTTPException(404, "Student not found")
    return student


def student_summary(db: Session, student: models.User) -> dict:
    profile = db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == student.id))
    attempts = db.execute(
        select(models.AssessmentAttempt.score_percent, models.AssessmentAttempt.created_at)
        .where(models.AssessmentAttempt.user_id == student.id)
        .order_by(models.AssessmentAttempt.created_at.desc())
    ).all()
    scores = [a.score_percent for a in attempts]
    last_assessment = _aware(attempts[0].created_at) if attempts else None
    progress = db.execute(
        select(models.LearningProgress.status, func.count())
        .where(models.LearningProgress.user_id == student.id)
        .group_by(models.LearningProgress.status)
    ).all()
    counts = {s: n for s, n in progress}

    career = None
    if profile and profile.target_career_id:
        role = db.scalar(
            select(models.CareerRole)
            .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
            .where(models.CareerRole.id == profile.target_career_id)
        )
        if role:
            levels = dict(db.execute(
                select(models.StudentSkill.skill_id, models.StudentSkill.level)
                .where(models.StudentSkill.user_id == student.id)
            ).all())
            score, rows = career_alignment(role.skills, levels)
            career = {
                "id": role.id, "name": role.name, "alignment_score": score,
                "high_priority_gaps": [r["skill"] for r in rows if r["priority"] == "High"],
            }

    avg = round(sum(scores) / len(scores), 1) if scores else None
    reasons = []
    if not attempts:
        reasons.append("No assessments taken yet")
    elif last_assessment < utcnow() - timedelta(days=INACTIVE_DAYS):
        reasons.append(f"No assessment in the last {INACTIVE_DAYS} days")
    if avg is not None and avg < LOW_AVERAGE:
        reasons.append(f"Average score below {LOW_AVERAGE:g}%")
    if career is None:
        reasons.append("No target career selected")
    elif attempts and career["alignment_score"] < LOW_ALIGNMENT:
        reasons.append(f"Career alignment below {LOW_ALIGNMENT}%")
    if not counts:
        reasons.append("Not tracking any learning resources")

    return {
        "id": student.id,
        "full_name": student.full_name,
        "email": student.email,
        "is_active": student.is_active,
        "college": profile.college if profile else None,
        "department": profile.department if profile else None,
        "current_semester": profile.current_semester if profile else None,
        "target_career": career,
        "assessments": {"count": len(scores), "average_score": avg, "last_at": last_assessment},
        "learning": {"completed": counts.get("completed", 0), "in_progress": counts.get("in_progress", 0)},
        "needs_attention": reasons,
    }
