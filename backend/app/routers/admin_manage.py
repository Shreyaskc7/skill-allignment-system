"""Administration: system statistics, user accounts, catalogue (skills, career roles, resources), audit log.

Every mutation here is recorded in the audit log. Students and teachers receive 403.
Safety rules for accounts: an administrator cannot deactivate or demote themselves,
and the last active administrator can never be deactivated or demoted.
"""

import json
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app import models
from app.db import get_db
from app.deps import require_admin
from app.models import UserRole
from app.security import utcnow
from app.services.audit import audit
from app.services.auth import revoke_all_refresh_tokens
from app.services.learning import RESOURCE_TYPES

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

Difficulty = Literal["beginner", "intermediate", "advanced"]


def _strip(v):
    if isinstance(v, str):
        v = " ".join(v.split()) if "\n" not in v else v.strip()
        return v or None
    return v


# ------------------------------------------------------------------ statistics

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    since = utcnow() - timedelta(days=30)
    users = dict(db.execute(select(models.User.role, func.count()).where(models.User.is_active.is_(True))
                            .group_by(models.User.role)).all())
    submitted = models.AssessmentAttempt.status == "submitted"
    return {
        "users": {r.value: users.get(r, 0) for r in UserRole},
        "inactive_users": count(select(func.count(models.User.id)).where(models.User.is_active.is_(False))),
        "pending_invitations": count(select(func.count(models.TeacherInvitation.id)).where(
            models.TeacherInvitation.accepted_at.is_(None), models.TeacherInvitation.revoked_at.is_(None),
            models.TeacherInvitation.expires_at > utcnow())),
        "active_assignments": count(select(func.count(models.StudentTeacherAssignment.id))
                                    .where(models.StudentTeacherAssignment.is_active.is_(True))),
        "assessments_total": count(select(func.count(models.AssessmentAttempt.id)).where(submitted)),
        "assessments_last_30_days": count(select(func.count(models.AssessmentAttempt.id)).where(
            submitted, models.AssessmentAttempt.submitted_at >= since)),
        "average_score": round(db.scalar(select(func.avg(models.AssessmentAttempt.score_percent)).where(submitted)) or 0, 1),
        "skills": count(select(func.count(models.Skill.id))),
        "career_roles_active": count(select(func.count(models.CareerRole.id)).where(models.CareerRole.is_active.is_(True))),
        "questions_active": count(select(func.count(models.AssessmentQuestion.id))
                                  .where(models.AssessmentQuestion.is_active.is_(True))),
        "resources": count(select(func.count(models.LearningResource.id))),
        "jobs_active": count(select(func.count(models.JobPosting.id)).where(models.JobPosting.is_active.is_(True))),
        "logins_last_30_days": count(select(func.count(models.AuditLog.id)).where(
            models.AuditLog.action == "auth.login", models.AuditLog.created_at >= since)),
    }


# ------------------------------------------------------------------ users

class UserPatch(BaseModel):
    is_active: bool | None = None
    role: Literal["student", "teacher", "admin"] | None = None
    reason: str | None = Field(None, max_length=300)


def _user_out(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role.value, "is_active": u.is_active,
            "is_verified": u.is_verified, "created_at": u.created_at, "last_login_at": u.last_login_at}


@router.get("/accounts")
def list_accounts(role: str | None = None, active: bool | None = None, search: str | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db)):
    stmt = select(models.User)
    if role:
        try:
            stmt = stmt.where(models.User.role == UserRole(role))
        except ValueError:
            raise HTTPException(422, "Unknown role") from None
    if active is not None:
        stmt = stmt.where(models.User.is_active.is_(active))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(models.User.full_name.ilike(like) | models.User.email.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(models.User.created_at.desc(), models.User.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    return {"items": [_user_out(u) for u in rows], "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size}


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count(models.User.id)).where(
        models.User.role == UserRole.admin, models.User.is_active.is_(True))) or 0


@router.patch("/accounts/{user_id}")
def update_account(user_id: int, body: UserPatch, request: Request, admin: models.User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    new_role = UserRole(body.role) if body.role else user.role
    deactivating = body.is_active is False and user.is_active
    demoting = user.role == UserRole.admin and new_role != UserRole.admin
    if user.id == admin.id and (deactivating or demoting):
        raise HTTPException(409, "You cannot deactivate or demote your own account")
    if user.role == UserRole.admin and user.is_active and (deactivating or demoting) and _active_admins(db) <= 1:
        raise HTTPException(409, "At least one active administrator must remain")

    changes = {}
    if new_role != user.role:
        # End assignments that no longer make sense for the new role (history is kept).
        now = utcnow()
        col = (models.StudentTeacherAssignment.student_id if user.role == UserRole.student
               else models.StudentTeacherAssignment.teacher_id)
        db.execute(update(models.StudentTeacherAssignment)
                   .where(col == user.id, models.StudentTeacherAssignment.is_active.is_(True))
                   .values(is_active=False, removed_at=now, removal_reason=f"Role changed to {new_role.value}"))
        if new_role == UserRole.teacher and db.scalar(select(models.TeacherProfile).where(models.TeacherProfile.user_id == user.id)) is None:
            db.add(models.TeacherProfile(user_id=user.id))
        if new_role == UserRole.student and db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == user.id)) is None:
            db.add(models.StudentProfile(user_id=user.id))
        changes["role"] = [user.role.value, new_role.value]
        user.role = new_role
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = [user.is_active, body.is_active]
        user.is_active = body.is_active
        if not body.is_active:
            revoke_all_refresh_tokens(db, user.id)  # sign the user out everywhere
    if changes:
        audit(db, "admin.user_updated", user_id=admin.id, entity_type="user", entity_id=user.id,
              details={**changes, "reason": body.reason}, request=request)
    db.commit()
    return _user_out(user)


# ------------------------------------------------------------------ skills

class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=60)
    description: str | None = Field(None, max_length=2000)
    esco_identifier: str | None = Field(None, max_length=50)
    esco_label: str | None = Field(None, max_length=200)

    _clean = field_validator("name", "category", "description", "esco_identifier", "esco_label", mode="before")(
        classmethod(lambda cls, v: _strip(v)))


def _skill_out(s: models.Skill) -> dict:
    return {"id": s.id, "name": s.name, "category": s.category, "description": s.description,
            "esco_identifier": s.esco_identifier, "esco_label": s.esco_label}


def _unique_skill_name(db: Session, name: str, exclude: int | None = None):
    if db.scalar(select(models.Skill.id).where(func.lower(models.Skill.name) == name.lower(),
                                               models.Skill.id != (exclude or -1))):
        raise HTTPException(409, "A skill with this name already exists")


@router.post("/skills", status_code=201)
def create_skill(body: SkillIn, request: Request, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    _unique_skill_name(db, body.name)
    s = models.Skill(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, "admin.skill_created", user_id=admin.id, entity_type="skill", entity_id=s.id, request=request)
    db.commit()
    return _skill_out(s)


@router.put("/skills/{skill_id}")
def update_skill(skill_id: int, body: SkillIn, request: Request, admin: models.User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    s = db.get(models.Skill, skill_id)
    if s is None:
        raise HTTPException(404, "Skill not found")
    _unique_skill_name(db, body.name, exclude=s.id)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit(db, "admin.skill_updated", user_id=admin.id, entity_type="skill", entity_id=s.id, request=request)
    db.commit()
    return _skill_out(s)


# ------------------------------------------------------------------ career roles

class RequirementIn(BaseModel):
    skill_id: int
    required_level: int = Field(ge=1, le=5)
    importance_weight: int = Field(ge=1, le=5)


class CareerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field("", max_length=2000)
    is_active: bool = True
    requirements: list[RequirementIn] = Field(min_length=1, max_length=30)

    _clean = field_validator("name", mode="before")(classmethod(lambda cls, v: _strip(v)))


def _career_out(c: models.CareerRole) -> dict:
    return {"id": c.id, "name": c.name, "description": c.description, "is_active": c.is_active,
            "requirements": [{"skill_id": r.skill_id, "skill": r.skill.name, "required_level": r.required_level,
                              "importance_weight": r.importance_weight} for r in c.skills]}


def _load_career(db: Session, career_id: int) -> models.CareerRole:
    c = db.scalar(select(models.CareerRole).options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
                  .where(models.CareerRole.id == career_id))
    if c is None:
        raise HTTPException(404, "Career role not found")
    return c


def _set_requirements(db: Session, career: models.CareerRole, reqs: list[RequirementIn]):
    ids = [r.skill_id for r in reqs]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Each skill can be required only once")
    if unknown := sorted(set(ids) - set(db.scalars(select(models.Skill.id).where(models.Skill.id.in_(ids))))):
        raise HTTPException(422, f"Unknown skill id(s): {unknown}")
    career.skills.clear()
    db.flush()
    for r in reqs:
        career.skills.append(models.CareerRoleSkill(skill_id=r.skill_id, required_level=r.required_level,
                                                    importance_weight=r.importance_weight))


@router.get("/careers")
def list_careers(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.CareerRole).options(
        selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill)).order_by(models.CareerRole.name))
    return [_career_out(c) for c in rows]


@router.post("/careers", status_code=201)
def create_career(body: CareerIn, request: Request, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(models.CareerRole.id).where(func.lower(models.CareerRole.name) == body.name.lower())):
        raise HTTPException(409, "A career role with this name already exists")
    c = models.CareerRole(name=body.name, description=body.description, is_active=body.is_active)
    db.add(c)
    db.flush()
    _set_requirements(db, c, body.requirements)
    audit(db, "admin.career_created", user_id=admin.id, entity_type="career_role", entity_id=c.id, request=request)
    db.commit()
    return _career_out(_load_career(db, c.id))


@router.put("/careers/{career_id}")
def update_career(career_id: int, body: CareerIn, request: Request, admin: models.User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    c = _load_career(db, career_id)
    if db.scalar(select(models.CareerRole.id).where(func.lower(models.CareerRole.name) == body.name.lower(),
                                                    models.CareerRole.id != c.id)):
        raise HTTPException(409, "A career role with this name already exists")
    c.name, c.description, c.is_active = body.name, body.description, body.is_active
    _set_requirements(db, c, body.requirements)
    audit(db, "admin.career_updated", user_id=admin.id, entity_type="career_role", entity_id=c.id,
          details={"requirements": len(body.requirements), "is_active": body.is_active}, request=request)
    db.commit()
    return _career_out(_load_career(db, c.id))


# ------------------------------------------------------------------ learning resources

class ResourceIn(BaseModel):
    skill_id: int
    title: str = Field(min_length=2, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    url: str = Field(max_length=500, pattern=r"^https?://\S+$")
    resource_type: str
    difficulty: Difficulty
    description: str = Field("", max_length=2000)
    is_free: bool = True
    estimated_hours: int | None = Field(None, ge=1, le=500)

    @field_validator("resource_type")
    @classmethod
    def known_type(cls, v):
        if v not in RESOURCE_TYPES:
            raise ValueError(f"resource_type must be one of {', '.join(RESOURCE_TYPES)}")
        return v


def _resource_out(r: models.LearningResource) -> dict:
    return {"id": r.id, "skill_id": r.skill_id, "title": r.title, "provider": r.provider, "url": r.url,
            "resource_type": r.resource_type, "difficulty": r.difficulty, "description": r.description,
            "is_free": r.is_free, "estimated_hours": r.estimated_hours}


def _check_resource(db: Session, body: ResourceIn, exclude: int | None = None):
    if db.get(models.Skill, body.skill_id) is None:
        raise HTTPException(422, "Unknown skill")
    if db.scalar(select(models.LearningResource.id).where(
            models.LearningResource.skill_id == body.skill_id, models.LearningResource.title == body.title,
            models.LearningResource.id != (exclude or -1))):
        raise HTTPException(409, "This skill already has a resource with the same title")


@router.post("/resources", status_code=201)
def create_resource(body: ResourceIn, request: Request, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    _check_resource(db, body)
    r = models.LearningResource(**body.model_dump())
    db.add(r)
    db.flush()
    audit(db, "admin.resource_created", user_id=admin.id, entity_type="learning_resource", entity_id=r.id, request=request)
    db.commit()
    return _resource_out(r)


@router.put("/resources/{resource_id}")
def update_resource(resource_id: int, body: ResourceIn, request: Request, admin: models.User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    r = db.get(models.LearningResource, resource_id)
    if r is None:
        raise HTTPException(404, "Resource not found")
    _check_resource(db, body, exclude=r.id)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit(db, "admin.resource_updated", user_id=admin.id, entity_type="learning_resource", entity_id=r.id, request=request)
    db.commit()
    return _resource_out(r)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int, request: Request, admin: models.User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    r = db.get(models.LearningResource, resource_id)
    if r is None:
        raise HTTPException(404, "Resource not found")
    if db.scalar(select(func.count(models.LearningProgress.id)).where(models.LearningProgress.resource_id == r.id)):
        raise HTTPException(409, "Students have progress on this resource; edit it instead of deleting it")
    audit(db, "admin.resource_deleted", user_id=admin.id, entity_type="learning_resource", entity_id=r.id,
          details={"title": r.title}, request=request)
    db.delete(r)
    db.commit()


# ------------------------------------------------------------------ audit log

@router.get("/audit")
def audit_log(action: str | None = None, user_id: int | None = None, entity_type: str | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(models.AuditLog, models.User.email).outerjoin(models.User, models.User.id == models.AuditLog.user_id)
    if action:
        stmt = stmt.where(models.AuditLog.action.ilike(f"{action.strip()}%"))
    if user_id:
        stmt = stmt.where(models.AuditLog.user_id == user_id)
    if entity_type:
        stmt = stmt.where(models.AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [{"id": a.id, "action": a.action, "user_id": a.user_id, "user_email": email,
                   "entity_type": a.entity_type, "entity_id": a.entity_id,
                   "details": json.loads(a.details) if a.details else None, "ip_address": a.ip_address,
                   "created_at": a.created_at} for a, email in rows],
        "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
    }
