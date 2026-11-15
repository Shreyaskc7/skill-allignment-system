"""Security utilities: password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.hash import argon2
import jwt

from app.config import settings


_argon2 = argon2.using(
    type="ID",
    rounds=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost_kib,
    parallelism=settings.argon2_parallelism,
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id (OWASP-recommended cost parameters)."""
    return _argon2.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return argon2.verify(password, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=settings.refresh_token_expire_days))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.refresh_secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> Optional[dict]:
    payload = decode_token(token, settings.secret_key)
    if payload and payload.get("type") == "access":
        return payload
    return None


def decode_refresh_token(token: str) -> Optional[dict]:
    payload = decode_token(token, settings.refresh_secret)
    if payload and payload.get("type") == "refresh":
        return payload
    return None