"""Administrator endpoints (Phase 3: teacher invitations; Phase 10 adds the rest)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_admin
from app.schemas import AssignmentEnd, AssignmentIn, InvitationCreate, InvitationCreated, InvitationOut
from app.security import utcnow
from app.services import auth as svc
from app.services.audit import audit

router = APIRouter(prefix="/admin", tags=["admin"])


def _out(inv: models.TeacherInvitation, **extra) -> dict:
    return {
        "id": inv.id,
        "email": inv.email,
        "full_name": inv.full_name,
        "expires_at": inv.expires_at,
        "accepted_at": inv.accepted_at,
        "revoked_at": inv.revoked_at,
        "created_at": inv.created_at,
        "status": svc.invitation_status(inv),
        **extra,
    }


@router.post("/invitations", response_model=InvitationCreated, status_code=201)
def create_invitation(
    body: InvitationCreate, request: Request, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    inv, link = svc.create_invitation(db, body.email, body.full_name, admin, request)
    db.refresh(inv)
    # The link is also returned so an administrator can share it when SMTP is not configured.
    return _out(inv, invite_url=link)


@router.get("/invitations", response_model=list[InvitationOut])
def list_invitations(_: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(models.TeacherInvitation).order_by(models.TeacherInvitation.created_at.desc())).all()
    return [_out(i) for i in rows]


@router.post("/invitations/{invitation_id}/revoke", response_model=InvitationOut)
def revoke_invitation(
    invitation_id: int, request: Request, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    inv = db.get(models.TeacherInvitation, invitation_id)
    if inv is None:
        raise HTTPException(404, "Invitation not found")
    if svc.invitation_status(inv) != "pending":
        raise HTTPException(400, "Only pending invitations can be revoked")
    inv.revoked_at = utcnow()
    audit(db, "admin.invitation_revoked", user_id=admin.id, entity_type="teacher_invitation", entity_id=inv.id,
          request=request)
    db.commit()
    return _out(inv)


# ------------------------------------------------------------------ users (for assignment pickers)

@router.get("/users")
def list_users(role: str | None = None, search: str | None = None,
               _: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(models.User).order_by(models.User.full_name)
    if role:
        try:
            stmt = stmt.where(models.User.role == models.UserRole(role))
        except ValueError:
            raise HTTPException(422, "Unknown role") from None
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(models.User.full_name.ilike(like) | models.User.email.ilike(like))
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role.value, "is_active": u.is_active}
        for u in db.scalars(stmt.limit(500))
    ]


# ------------------------------------------------------------------ student-mentor assignments

def _assignment_out(db: Session, a: models.StudentTeacherAssignment, users: dict[int, models.User] | None = None) -> dict:
    get = (lambda uid: users[uid]) if users is not None else (lambda uid: db.get(models.User, uid))
    s, t = get(a.student_id), get(a.teacher_id)
    by = get(a.assigned_by) if a.assigned_by else None
    return {
        "id": a.id, "student_id": s.id, "student_name": s.full_name, "student_email": s.email,
        "teacher_id": t.id, "teacher_name": t.full_name, "assigned_by": by.full_name if by else None,
        "assigned_at": a.assigned_at, "is_active": a.is_active, "removed_at": a.removed_at,
        "removal_reason": a.removal_reason,
    }


@router.get("/assignments")
def list_assignments(active: bool | None = None, student_id: int | None = None, teacher_id: int | None = None,
                     _: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(models.StudentTeacherAssignment).order_by(
        models.StudentTeacherAssignment.assigned_at.desc(), models.StudentTeacherAssignment.id.desc())
    if active is not None:
        stmt = stmt.where(models.StudentTeacherAssignment.is_active.is_(active))
    if student_id:
        stmt = stmt.where(models.StudentTeacherAssignment.student_id == student_id)
    if teacher_id:
        stmt = stmt.where(models.StudentTeacherAssignment.teacher_id == teacher_id)
    rows = list(db.scalars(stmt))
    ids = {x for a in rows for x in (a.student_id, a.teacher_id, a.assigned_by) if x}
    users = {u.id: u for u in db.scalars(select(models.User).where(models.User.id.in_(ids or {-1})))}  # one query
    return [_assignment_out(db, a, users) for a in rows]


@router.post("/assignments", status_code=201)
def create_assignment(body: AssignmentIn, request: Request, admin: models.User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    student, teacher = db.get(models.User, body.student_id), db.get(models.User, body.teacher_id)
    if student is None or student.role != models.UserRole.student or not student.is_active:
        raise HTTPException(422, "Choose an active student")
    if teacher is None or teacher.role != models.UserRole.teacher or not teacher.is_active:
        raise HTTPException(422, "Choose an active teacher/mentor")
    existing = db.scalar(select(models.StudentTeacherAssignment).where(
        models.StudentTeacherAssignment.student_id == student.id,
        models.StudentTeacherAssignment.teacher_id == teacher.id,
        models.StudentTeacherAssignment.is_active.is_(True),
    ))
    if existing:
        raise HTTPException(409, "This student is already assigned to this mentor")
    a = models.StudentTeacherAssignment(student_id=student.id, teacher_id=teacher.id, assigned_by=admin.id,
                                        is_active=True)
    db.add(a)
    db.flush()
    audit(db, "admin.assignment_created", user_id=admin.id, entity_type="assignment", entity_id=a.id,
          details={"student_id": student.id, "teacher_id": teacher.id}, request=request)
    db.commit()
    db.refresh(a)
    return _assignment_out(db, a)


@router.post("/assignments/{assignment_id}/end")
def end_assignment(assignment_id: int, body: AssignmentEnd, request: Request,
                   admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(models.StudentTeacherAssignment, assignment_id)
    if a is None:
        raise HTTPException(404, "Assignment not found")
    if not a.is_active:
        raise HTTPException(400, "This assignment has already ended")
    a.is_active, a.removed_at, a.removal_reason = False, utcnow(), body.reason.strip()
    audit(db, "admin.assignment_ended", user_id=admin.id, entity_type="assignment", entity_id=a.id,
          details={"reason": a.removal_reason}, request=request)
    db.commit()
    return _assignment_out(db, a)
