"""Administrator endpoints (Phase 3: teacher invitations; Phase 10 adds the rest)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_admin
from app.schemas import InvitationCreate, InvitationCreated, InvitationOut
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
