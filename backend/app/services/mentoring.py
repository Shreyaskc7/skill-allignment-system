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


def student_summaries(db: Session, students: list[models.User]) -> list[dict]:
    """Summaries for many students with a fixed number of queries (no per-student round trips)."""
    ids = [s.id for s in students] or [-1]
    profiles = {p.user_id: p for p in db.scalars(select(models.StudentProfile).where(models.StudentProfile.user_id.in_(ids)))}
    scores: dict[int, list[float]] = {}
    last: dict[int, object] = {}
    for uid, score, created in db.execute(
        select(models.AssessmentAttempt.user_id, models.AssessmentAttempt.score_percent, models.AssessmentAttempt.created_at)
        .where(models.AssessmentAttempt.user_id.in_(ids), models.AssessmentAttempt.status == "submitted")
    ).all():
        scores.setdefault(uid, []).append(score)
        if created is not None and (uid not in last or _aware(created) > last[uid]):
            last[uid] = _aware(created)
    counts: dict[int, dict[str, int]] = {}
    for uid, status, n in db.execute(
        select(models.LearningProgress.user_id, models.LearningProgress.status, func.count())
        .where(models.LearningProgress.user_id.in_(ids))
        .group_by(models.LearningProgress.user_id, models.LearningProgress.status)
    ).all():
        counts.setdefault(uid, {})[status] = n
    levels: dict[int, dict[int, int]] = {}
    for uid, sid, lvl in db.execute(
        select(models.StudentSkill.user_id, models.StudentSkill.skill_id, models.StudentSkill.level)
        .where(models.StudentSkill.user_id.in_(ids))
    ).all():
        levels.setdefault(uid, {})[sid] = lvl
    career_ids = {p.target_career_id for p in profiles.values() if p.target_career_id}
    roles = {r.id: r for r in db.scalars(
        select(models.CareerRole).options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
        .where(models.CareerRole.id.in_(career_ids or {-1})))}
    return [_summarise(st, profiles.get(st.id), scores.get(st.id, []), last.get(st.id), counts.get(st.id, {}),
                       levels.get(st.id, {}), roles) for st in students]


def student_summary(db: Session, student: models.User) -> dict:
    return student_summaries(db, [student])[0]


def _summarise(student, profile, scores, last_assessment, counts, levels, roles) -> dict:
    career = None
    role = roles.get(profile.target_career_id) if profile and profile.target_career_id else None
    if role:
        score, rows = career_alignment(role.skills, levels)
        career = {
            "id": role.id, "name": role.name, "alignment_score": score,
            "high_priority_gaps": [r["skill"] for r in rows if r["priority"] == "High"],
        }

    avg = round(sum(scores) / len(scores), 1) if scores else None
    reasons = []
    if not scores:
        reasons.append("No assessments taken yet")
    elif last_assessment is not None and last_assessment < utcnow() - timedelta(days=INACTIVE_DAYS):
        reasons.append(f"No assessment in the last {INACTIVE_DAYS} days")
    if avg is not None and avg < LOW_AVERAGE:
        reasons.append(f"Average score below {LOW_AVERAGE:g}%")
    if career is None:
        reasons.append("No target career selected")
    elif scores and career["alignment_score"] < LOW_ALIGNMENT:
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
