"""The signed-in student's own profile, files, self-reported skills and dashboard.

Every route is under /students/me and resolves the student from the access
token, so one student can never address another student's records.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_student
from app.schemas import SelfSkillOut, SelfSkillsIn, StudentProfileIn, StudentProfileView
from app.services import uploads
from app.services.audit import audit
from app.services.dashboard import student_dashboard
from app.services.profile import completion, get_or_create_profile

router = APIRouter(prefix="/students/me", tags=["student profile"])

PROFILE_FIELDS = [f for f in StudentProfileIn.model_fields if f != "full_name"]


def _view(db: Session, user: models.User, p: models.StudentProfile) -> dict:
    career = db.get(models.CareerRole, p.target_career_id) if p.target_career_id else None
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        **{f: getattr(p, f) for f in PROFILE_FIELDS},
        "target_career_name": career.name if career else None,
        "has_profile_image": uploads.path_for(p.profile_image_url) is not None,
        "has_resume": uploads.path_for(p.resume_url) is not None,
        "completion": completion(db, p),
    }


@router.get("/profile", response_model=StudentProfileView)
def get_profile(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    p = get_or_create_profile(db, user)
    db.commit()
    return _view(db, user, p)


@router.put("/profile", response_model=StudentProfileView)
def update_profile(
    body: StudentProfileIn, request: Request,
    user: models.User = Depends(require_student), db: Session = Depends(get_db),
):
    if body.target_career_id is not None:
        career = db.get(models.CareerRole, body.target_career_id)
        if career is None or not career.is_active:
            raise HTTPException(422, "Unknown target career")
    p = get_or_create_profile(db, user)
    user.full_name = body.full_name
    for f in PROFILE_FIELDS:
        setattr(p, f, getattr(body, f))
    audit(db, "student.profile_updated", user_id=user.id, entity_type="student_profile", entity_id=p.id, request=request)
    db.commit()
    return _view(db, user, p)


@router.put("/target-career", response_model=StudentProfileView)
def set_target_career(
    body: dict, user: models.User = Depends(require_student), db: Session = Depends(get_db)
):
    """Quick target-career change from the dashboard (the full form uses PUT /profile)."""
    cid = body.get("target_career_id")
    if cid is not None:
        if not isinstance(cid, int) or (c := db.get(models.CareerRole, cid)) is None or not c.is_active:
            raise HTTPException(422, "Unknown target career")
    p = get_or_create_profile(db, user)
    p.target_career_id = cid
    db.commit()
    return _view(db, user, p)


# ------------------------------------------------------------------ files

def _file_routes(name: str, kind: uploads.Kind, column: str):
    @router.post(f"/{name}", response_model=StudentProfileView, name=f"upload_{name}")
    async def upload(
        request: Request, file: UploadFile = File(...),
        user: models.User = Depends(require_student), db: Session = Depends(get_db),
    ):
        key = await uploads.save(file, kind)
        p = get_or_create_profile(db, user)
        old = getattr(p, column)
        setattr(p, column, key)
        audit(db, f"student.{name}_uploaded", user_id=user.id, request=request)
        db.commit()
        uploads.delete(old)
        return _view(db, user, p)

    @router.get(f"/{name}", name=f"download_{name}")
    def download(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
        p = get_or_create_profile(db, user)
        path = uploads.path_for(getattr(p, column))
        if path is None:
            raise HTTPException(404, "No file uploaded")
        return FileResponse(
            path, media_type=uploads.MEDIA_TYPES[path.suffix[1:]],
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
            content_disposition_type="inline", filename=f"{name}{path.suffix}",
        )

    @router.delete(f"/{name}", response_model=StudentProfileView, name=f"delete_{name}")
    def remove(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
        p = get_or_create_profile(db, user)
        old = getattr(p, column)
        setattr(p, column, None)
        db.commit()
        uploads.delete(old)
        return _view(db, user, p)


_file_routes("photo", uploads.IMAGE, "profile_image_url")
_file_routes("resume", uploads.RESUME, "resume_url")


# ------------------------------------------------------------------ self-reported skills

def _self_skills(db: Session, user: models.User) -> list[dict]:
    rows = db.execute(
        select(models.StudentSelfSkill, models.Skill)
        .join(models.Skill, models.Skill.id == models.StudentSelfSkill.skill_id)
        .where(models.StudentSelfSkill.user_id == user.id)
        .order_by(models.Skill.category, models.Skill.name)
    ).all()
    return [{"skill_id": s.id, "skill_name": s.name, "category": s.category, "level": r.level} for r, s in rows]


@router.get("/self-skills", response_model=list[SelfSkillOut])
def get_self_skills(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    return _self_skills(db, user)


@router.put("/self-skills", response_model=list[SelfSkillOut])
def replace_self_skills(
    body: SelfSkillsIn, user: models.User = Depends(require_student), db: Session = Depends(get_db)
):
    ids = [s.skill_id for s in body.skills]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Each skill can be listed only once")
    known = set(db.scalars(select(models.Skill.id).where(models.Skill.id.in_(ids)))) if ids else set()
    if unknown := sorted(set(ids) - known):
        raise HTTPException(422, f"Unknown skill id(s): {unknown}")
    db.execute(delete(models.StudentSelfSkill).where(models.StudentSelfSkill.user_id == user.id))
    db.add_all(models.StudentSelfSkill(user_id=user.id, skill_id=s.skill_id, level=s.level) for s in body.skills)
    db.commit()
    return _self_skills(db, user)


# ------------------------------------------------------------------ dashboard

@router.get("/dashboard")
def dashboard(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    data = student_dashboard(db, user)
    db.commit()  # profile may have been created lazily
    return data
