"""Password hashing (Argon2id), access tokens (JWT) and opaque random tokens."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost_kib,
    parallelism=settings.argon2_parallelism,
)
JWT_ALGORITHM = "HS256"

# Used to spend the same time on unknown emails as on wrong passwords.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    """Hash a password using Argon2id (OWASP-recommended cost parameters)."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    """Constant-effort verification; malformed or empty hashes never verify."""
    try:
        return _hasher.verify(hashed or _DUMMY_HASH, password) and bool(hashed)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub", "type"]}
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None


def new_opaque_token() -> str:
    """URL-safe random token for refresh cookies, password resets and invitations."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Tokens are stored only as SHA-256 hashes (they are high-entropy, so no salt is needed)."""
    return hashlib.sha256(token.encode()).hexdigest()
