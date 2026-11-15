"""Mentor workspace: dashboard, assigned students, student detail and mentoring notes.

Teachers see only students actively assigned to them; administrators see all.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.deps import require_staff
from app.models import UserRole
from app.schemas import MentoringNoteIn
from app.services.alignment import career_alignment
from app.services.audit import audit
from app.services.mentoring import get_viewable_student, student_summary, visible_student_ids

router = APIRouter(prefix="/mentor", tags=["mentor"])


def _students(db: Session, viewer: models.User, search: str | None = None) -> list[models.User]:
    stmt = select(models.User).where(models.User.role == UserRole.student, models.User.is_active.is_(True))
    allowed = visible_student_ids(db, viewer)
    if allowed is not None:
        stmt = stmt.where(models.User.id.in_(allowed or [-1]))
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(models.User.full_name.ilike(like) | models.User.email.ilike(like))
    return list(db.scalars(stmt.order_by(models.User.full_name)))


@router.get("/students")
def list_students(search: str | None = None, viewer: models.User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    return [student_summary(db, s) for s in _students(db, viewer, search)]


@router.get("/dashboard")
def dashboard(viewer: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    summaries = [student_summary(db, s) for s in _students(db, viewer)]
    with_scores = [s["assessments"]["average_score"] for s in summaries if s["assessments"]["average_score"] is not None]
    aligned = [s["target_career"]["alignment_score"] for s in summaries if s["target_career"]]
    return {
        "scope": "all students" if viewer.role == UserRole.admin else "assigned students",
        "total_students": len(summaries),
        "participating": sum(1 for s in summaries if s["assessments"]["count"]),
        "average_score": round(sum(with_scores) / len(with_scores), 1) if with_scores else None,
        "average_alignment": round(sum(aligned) / len(aligned)) if aligned else None,
        "resources_completed": sum(s["learning"]["completed"] for s in summaries),
        "needs_attention": [
            {"id": s["id"], "full_name": s["full_name"], "reasons": s["needs_attention"]}
            for s in summaries if s["needs_attention"]
        ],
    }


@router.get("/students/{student_id}")
def student_detail(student_id: int, viewer: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    student = get_viewable_student(db, viewer, student_id)
    profile = db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == student.id))
    attempts = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == student.id)
        .order_by(models.AssessmentAttempt.created_at.desc())
    ).all()
    by_skill: dict[str, list[float]] = {}
    for a, name in attempts:
        by_skill.setdefault(name, []).append(a.score_percent)

    levels = dict(db.execute(
        select(models.StudentSkill.skill_id, models.StudentSkill.level).where(models.StudentSkill.user_id == student.id)
    ).all())
    gaps = None
    if profile and profile.target_career_id:
        role = db.scalar(
            select(models.CareerRole)
            .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
            .where(models.CareerRole.id == profile.target_career_id)
        )
        if role:
            score, rows = career_alignment(role.skills, levels)
            gaps = {"career": role.name, "alignment_score": score, "skills": rows}

    progress = db.execute(
        select(models.LearningProgress, models.LearningResource.title, models.Skill.name)
        .join(models.LearningResource, models.LearningResource.id == models.LearningProgress.resource_id)
        .join(models.Skill, models.Skill.id == models.LearningResource.skill_id)
        .where(models.LearningProgress.user_id == student.id)
        .order_by(models.LearningProgress.updated_at.desc())
    ).all()
    self_skills = db.execute(
        select(models.StudentSelfSkill.level, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.StudentSelfSkill.skill_id)
        .where(models.StudentSelfSkill.user_id == student.id)
    ).all()

    # Mentors see profile details relevant to guidance; contact data such as date of birth is not exposed.
    return {
        "summary": student_summary(db, student),
        "profile": None if profile is None else {
            k: getattr(profile, k) for k in (
                "college", "degree", "department", "specialization", "current_semester", "graduation_year",
                "career_interests", "preferred_locations", "experience_level", "technical_skills", "soft_skills",
            )
        },
        "assessments": [
            {"id": a.id, "skill": name, "score_percent": a.score_percent, "correct": a.correct_answers,
             "total": a.total_questions, "created_at": a.created_at}
            for a, name in attempts
        ],
        # Topic-level breakdown needs per-question attempt records (Phase 6); skill-level is shown until then.
        "skill_performance": [
            {"skill": k, "attempts": len(v), "best": max(v), "latest": v[0], "average": round(sum(v) / len(v), 1)}
            for k, v in sorted(by_skill.items())
        ],
        "gaps": gaps,
        "learning": [
            {"resource": title, "skill": skill, "status": p.status, "updated_at": p.updated_at}
            for p, title, skill in progress
        ],
        "self_reported_skills": [{"skill": n, "level": lvl} for lvl, n in self_skills],
        "notes": _notes(db, student.id, include_private=True),
    }


def _notes(db: Session, student_id: int, include_private: bool) -> list[dict]:
    stmt = (
        select(models.MentoringNote, models.User.full_name)
        .join(models.User, models.User.id == models.MentoringNote.teacher_id)
        .options(selectinload(models.MentoringNote.resource))
        .where(models.MentoringNote.student_id == student_id)
        .order_by(models.MentoringNote.created_at.desc(), models.MentoringNote.id.desc())
    )
    if not include_private:
        stmt = stmt.where(models.MentoringNote.visible_to_student.is_(True))
    return [
        {
            "id": n.id, "teacher_id": n.teacher_id, "teacher_name": author, "note": n.note,
            "note_type": n.note_type, "visible_to_student": n.visible_to_student, "created_at": n.created_at,
            "resource": None if n.resource is None else {"id": n.resource.id, "title": n.resource.title, "url": n.resource.url},
        }
        for n, author in db.execute(stmt).all()
    ]


@router.post("/students/{student_id}/notes", status_code=201)
def add_note(student_id: int, body: MentoringNoteIn, request: Request,
             viewer: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    student = get_viewable_student(db, viewer, student_id)
    if body.note_type == "resource_recommendation" and body.resource_id is None:
        raise HTTPException(422, "Choose the resource you are recommending")
    if body.resource_id is not None and db.get(models.LearningResource, body.resource_id) is None:
        raise HTTPException(422, "Unknown learning resource")
    note = models.MentoringNote(
        teacher_id=viewer.id, student_id=student.id, note=body.note, note_type=body.note_type,
        resource_id=body.resource_id,
        visible_to_student=False if body.note_type == "concern" else body.visible_to_student,
    )
    db.add(note)
    db.flush()
    audit(db, "mentor.note_added", user_id=viewer.id, entity_type="mentoring_note", entity_id=note.id,
          details={"student_id": student.id, "type": body.note_type}, request=request)
    db.commit()
    return next(n for n in _notes(db, student.id, include_private=True) if n["id"] == note.id)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, request: Request, viewer: models.User = Depends(require_staff),
                db: Session = Depends(get_db)):
    note = db.get(models.MentoringNote, note_id)
    if note is None:
        raise HTTPException(404, "Note not found")
    get_viewable_student(db, viewer, note.student_id)  # scope check
    if note.teacher_id != viewer.id and viewer.role != UserRole.admin:
        raise HTTPException(403, "You can only delete your own notes")
    audit(db, "mentor.note_deleted", user_id=viewer.id, entity_type="mentoring_note", entity_id=note.id, request=request)
    db.delete(note)
    db.commit()


def student_visible_notes(db: Session, student_id: int) -> list[dict]:
    return _notes(db, student_id, include_private=False)
