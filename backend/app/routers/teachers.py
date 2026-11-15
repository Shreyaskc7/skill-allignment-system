"""The signed-in teacher/mentor's own profile and photo."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_roles
from app.models import UserRole
from app.schemas import TeacherProfileIn
from app.services import uploads
from app.services.audit import audit

router = APIRouter(prefix="/teachers/me", tags=["teacher profile"])
require_teacher = require_roles(UserRole.teacher)
FIELDS = [f for f in TeacherProfileIn.model_fields if f != "full_name"]


def _profile(db: Session, user: models.User) -> models.TeacherProfile:
    p = db.scalar(select(models.TeacherProfile).where(models.TeacherProfile.user_id == user.id))
    if p is None:
        p = models.TeacherProfile(user_id=user.id)
        db.add(p)
        db.flush()
    return p


def _view(user: models.User, p: models.TeacherProfile) -> dict:
    return {
        "user_id": user.id, "email": user.email, "full_name": user.full_name,
        **{f: getattr(p, f) for f in FIELDS},
        "has_profile_image": uploads.path_for(p.profile_image_url) is not None,
    }


@router.get("/profile")
def get_profile(user: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    p = _profile(db, user)
    db.commit()
    return _view(user, p)


@router.put("/profile")
def update_profile(body: TeacherProfileIn, request: Request,
                   user: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    p = _profile(db, user)
    user.full_name = body.full_name
    for f in FIELDS:
        setattr(p, f, getattr(body, f))
    audit(db, "teacher.profile_updated", user_id=user.id, entity_type="teacher_profile", entity_id=p.id, request=request)
    db.commit()
    return _view(user, p)


@router.post("/photo")
async def upload_photo(file: UploadFile = File(...), user: models.User = Depends(require_teacher),
                       db: Session = Depends(get_db)):
    key = await uploads.save(file, uploads.IMAGE)
    p = _profile(db, user)
    old, p.profile_image_url = p.profile_image_url, key
    db.commit()
    uploads.delete(old)
    return _view(user, p)


@router.get("/photo")
def get_photo(user: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    path = uploads.path_for(_profile(db, user).profile_image_url)
    if path is None:
        raise HTTPException(404, "No photo uploaded")
    return FileResponse(path, media_type=uploads.MEDIA_TYPES[path.suffix[1:]],
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/photo")
def delete_photo(user: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    p = _profile(db, user)
    old, p.profile_image_url = p.profile_image_url, None
    db.commit()
    uploads.delete(old)
    return _view(user, p)
