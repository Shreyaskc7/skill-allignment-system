"""Registration, login, session refresh, logout, password management and invitation acceptance."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import UserRole
from app.schemas import (
    AcceptInvitationRequest,
    AccessTokenResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InvitationPreview,
    LoginRequest,
    MessageOut,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.security import hash_password, hash_token, needs_rehash, utcnow, verify_password
from app.services import auth as svc
from app.services.audit import audit
from app.services.rate_limit import rate_limited

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")


@router.post("/register", response_model=UserOut, status_code=201, dependencies=[Depends(rate_limited("register"))])
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if svc.find_user_by_email(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    user = models.User(
        email=body.email,
        full_name=body.full_name,
        role=UserRole.student,
        password_hash=hash_password(body.password),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()
    db.add(models.StudentProfile(user_id=user.id, phone=body.phone))
    audit(db, "auth.register", user_id=user.id, request=request)
    db.commit()
    return user


@router.post("/login", response_model=AccessTokenResponse, dependencies=[Depends(rate_limited("login"))])
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = svc.find_user_by_email(db, body.email)
    if not verify_password(body.password, user.password_hash if user else None):
        audit(db, "auth.login_failed", user_id=user.id if user else None, request=request)
        db.commit()
        raise INVALID_LOGIN
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled. Contact an administrator.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = utcnow()
    session = svc.issue_session(db, user, response)
    audit(db, "auth.login", user_id=user.id, request=request)
    db.commit()
    return session


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    try:
        return svc.rotate_refresh_token(db, refresh_token, request, response)
    except HTTPException as exc:
        failed = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if not isinstance(exc, svc.RefreshRace):
            svc.clear_refresh_cookie(failed)
        return failed


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    if refresh_token:
        row = db.query(models.RefreshToken).filter_by(token_hash=hash_token(refresh_token)).first()
        if row and row.revoked_at is None:
            row.revoked_at = utcnow()
            audit(db, "auth.logout", user_id=row.user_id, request=request)
            db.commit()
    svc.clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=AccessTokenResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    svc.revoke_all_refresh_tokens(db, user.id)  # sign out every other device
    session = svc.issue_session(db, user, response)
    audit(db, "auth.password_changed", user_id=user.id, request=request)
    db.commit()
    return session


@router.post("/forgot-password", response_model=MessageOut, status_code=202,
             dependencies=[Depends(rate_limited("forgot"))])
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    svc.request_password_reset(db, body.email, request)
    return {"message": "If an account exists for that email, a password reset link has been sent."}


@router.post("/reset-password", response_model=MessageOut, dependencies=[Depends(rate_limited("reset"))])
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    svc.reset_password(db, body.token, body.password, request)
    return {"message": "Your password has been reset. Please log in."}


@router.get("/invitations/{token}", response_model=InvitationPreview, dependencies=[Depends(rate_limited("invite"))])
def preview_invitation(token: str, db: Session = Depends(get_db)):
    inv = svc.pending_invitation(db, token)
    return {"email": inv.email, "full_name": inv.full_name}


@router.post("/accept-invitation", response_model=UserOut, status_code=201,
             dependencies=[Depends(rate_limited("invite"))])
def accept_invitation(body: AcceptInvitationRequest, request: Request, db: Session = Depends(get_db)):
    return svc.accept_invitation(db, body.token, body.password, body.full_name, request)
