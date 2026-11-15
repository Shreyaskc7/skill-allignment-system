"""Authentication and authorization dependencies.

Every protected endpoint resolves the user from a Bearer access token and
re-checks the account in the database, so deactivating a user or changing a
role takes effect immediately (the role claim in the token is not trusted).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.models import UserRole
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise UNAUTHORIZED
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise UNAUTHORIZED
    try:
        user = db.get(models.User, int(payload["sub"]))
    except (TypeError, ValueError):
        raise UNAUTHORIZED from None
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: the current user must have one of ``roles``."""

    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return dependency


require_student = require_roles(UserRole.student)
require_staff = require_roles(UserRole.teacher, UserRole.admin)
require_admin = require_roles(UserRole.admin)
