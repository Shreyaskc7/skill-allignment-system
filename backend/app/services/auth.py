"""Authentication workflows: sessions, refresh-token rotation, password reset, invitations."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.models import UserRole
from app.schemas import AccessTokenResponse, UserOut
from app.security import create_access_token, hash_password, hash_token, new_opaque_token, utcnow
from app.services.audit import audit
from app.services.email import send_email


REUSE_GRACE_SECONDS = 15


class RefreshRace(HTTPException):
    """A just-rotated refresh token was presented again (e.g. two tabs at once)."""


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; PostgreSQL returns aware ones.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cookie_path() -> str:
    return f"{settings.api_v1_prefix}/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=_cookie_path(),
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=_cookie_path(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def find_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.email == email.strip().lower()))


def issue_session(db: Session, user: models.User, response: Response) -> AccessTokenResponse:
    """Create an access token and a new refresh token (cookie). Caller commits."""
    refresh = new_opaque_token()
    db.add(
        models.RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    set_refresh_cookie(response, refresh)
    return AccessTokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


def revoke_all_refresh_tokens(db: Session, user_id: int) -> None:
    db.execute(
        update(models.RefreshToken)
        .where(models.RefreshToken.user_id == user_id, models.RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def rotate_refresh_token(db: Session, raw: str | None, request: Request, response: Response) -> AccessTokenResponse:
    """Exchange a refresh token for a new session. Reuse of a revoked token revokes every session of that user."""
    invalid = HTTPException(401, "Session expired. Please log in again.")
    if not raw:
        raise invalid
    row = db.scalar(select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_token(raw)))
    if row is None:
        raise invalid
    if row.revoked_at is not None:
        if (utcnow() - _aware(row.revoked_at)).total_seconds() < REUSE_GRACE_SECONDS:
            # Benign race: two tabs refreshed at the same moment. Reject without ending sessions,
            # and without clearing the (shared) cookie, which already holds the winner's new token.
            raise RefreshRace(401, "Session was just refreshed elsewhere. Retry.")
        # A rotated-out token was presented again later: possible theft. End all sessions.
        revoke_all_refresh_tokens(db, row.user_id)
        audit(db, "auth.refresh_reuse_detected", user_id=row.user_id, request=request)
        db.commit()
        raise invalid
    user = db.get(models.User, row.user_id)
    if _aware(row.expires_at) <= utcnow() or user is None or not user.is_active:
        row.revoked_at = utcnow()
        db.commit()
        raise invalid
    row.revoked_at = utcnow()
    session = issue_session(db, user, response)
    db.commit()
    return session


# ---------------------------------------------------------------- password reset

def request_password_reset(db: Session, email: str, request: Request) -> None:
    """Always succeeds from the caller's point of view (no account enumeration)."""
    user = find_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    token = new_opaque_token()
    db.add(
        models.PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    audit(db, "auth.password_reset_requested", user_id=user.id, request=request)
    db.commit()
    link = f"{settings.frontend_origin.rstrip('/')}/reset-password?token={token}"
    send_email(
        user.email,
        "Reset your SkillAlign password",
        f"Hello {user.full_name},\n\nUse this link within {settings.password_reset_expire_minutes} minutes "
        f"to choose a new password:\n\n{link}\n\nIf you did not request this, you can ignore this email.",
    )


def reset_password(db: Session, token: str, new_password: str, request: Request) -> None:
    row = db.scalar(select(models.PasswordResetToken).where(models.PasswordResetToken.token_hash == hash_token(token)))
    if row is None or row.used_at is not None or _aware(row.expires_at) <= utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    user = db.get(models.User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    user.password_hash = hash_password(new_password)
    row.used_at = utcnow()
    # Invalidate every other outstanding reset link and every session.
    db.execute(
        update(models.PasswordResetToken)
        .where(models.PasswordResetToken.user_id == user.id, models.PasswordResetToken.used_at.is_(None))
        .values(used_at=utcnow())
    )
    revoke_all_refresh_tokens(db, user.id)
    audit(db, "auth.password_reset", user_id=user.id, request=request)
    db.commit()


# ---------------------------------------------------------------- teacher invitations

def invitation_status(inv: models.TeacherInvitation) -> str:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if _aware(inv.expires_at) <= utcnow():
        return "expired"
    return "pending"


def create_invitation(
    db: Session, email: str, full_name: str, admin: models.User, request: Request
) -> tuple[models.TeacherInvitation, str]:
    if find_user_by_email(db, email):
        raise HTTPException(409, "An account with this email already exists")
    # Supersede earlier pending invitations to the same address.
    db.execute(
        update(models.TeacherInvitation)
        .where(
            models.TeacherInvitation.email == email,
            models.TeacherInvitation.accepted_at.is_(None),
            models.TeacherInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    token = new_opaque_token()
    inv = models.TeacherInvitation(
        email=email,
        full_name=full_name,
        token_hash=hash_token(token),
        invited_by=admin.id,
        expires_at=utcnow() + timedelta(days=settings.teacher_invitation_expire_days),
    )
    db.add(inv)
    db.flush()
    audit(db, "admin.teacher_invited", user_id=admin.id, entity_type="teacher_invitation", entity_id=inv.id,
          details={"email": email}, request=request)
    db.commit()
    link = f"{settings.frontend_origin.rstrip('/')}/accept-invitation?token={token}"
    send_email(
        email,
        "You have been invited to SkillAlign as a mentor",
        f"Hello {full_name},\n\nAn administrator has invited you to join SkillAlign as a teacher/mentor. "
        f"Create your account within {settings.teacher_invitation_expire_days} days:\n\n{link}\n",
    )
    return inv, link


def pending_invitation(db: Session, token: str) -> models.TeacherInvitation:
    inv = db.scalar(select(models.TeacherInvitation).where(models.TeacherInvitation.token_hash == hash_token(token)))
    if inv is None or invitation_status(inv) != "pending":
        raise HTTPException(400, "This invitation is invalid, expired or already used.")
    return inv


def accept_invitation(db: Session, token: str, password: str, full_name: str | None, request: Request) -> models.User:
    inv = pending_invitation(db, token)
    if find_user_by_email(db, inv.email):
        raise HTTPException(409, "An account with this email already exists")
    user = models.User(
        email=inv.email,
        full_name=full_name or inv.full_name,
        role=UserRole.teacher,
        password_hash=hash_password(password),
        is_active=True,
        is_verified=True,  # the invitation link proves control of the email address
    )
    db.add(user)
    db.flush()
    db.add(models.TeacherProfile(user_id=user.id))
    inv.accepted_at = utcnow()
    audit(db, "auth.invitation_accepted", user_id=user.id, entity_type="teacher_invitation", entity_id=inv.id,
          request=request)
    db.commit()
    return user
