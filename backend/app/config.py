"""Application configuration.

All secrets come from environment variables. The ``.env`` file is local-only and
must never be committed. See ``.env.example`` for the required names.
"""

import logging
import secrets
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("skillalign.config")

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

INSECURE_SECRETS = {"", "CHANGE_ME_IN_PRODUCTION", "change_me"}


class Settings(BaseSettings):
    app_name: str = "Intelligent Workforce Skill Alignment System"
    app_env: str = "development"  # development | test | production
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/skill_alignment_db"
    # Public URL of the frontend: used for CORS and for links in emails.
    frontend_origin: str = "http://localhost:5173"
    # Comma-separated extra origins allowed by CORS (FRONTEND_ORIGIN is always allowed).
    frontend_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5176,http://127.0.0.1:5176"
    )
    # Deprecated in version 2: the schema is managed by Alembic. Ignored.
    create_tables_on_start: bool = False
    # Run `alembic upgrade head` automatically at startup (off by default; back up first).
    auto_migrate: bool = False

    # Security: loaded from the environment, never hardcoded.
    secret_key: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "skillalign_refresh"
    # Set true when served over HTTPS (required in production).
    cookie_secure: bool = False
    password_reset_expire_minutes: int = 30
    teacher_invitation_expire_days: int = 7

    # Argon2id cost: time_cost is the number of passes (not PBKDF2-style
    # iterations), so keep it small. 3 passes / 64 MiB follows OWASP guidance.
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 4

    # Uploaded profile images and resumes (outside any web root; served only through
    # authenticated endpoints). Relative paths are resolved from the backend directory.
    upload_dir: str = "uploads"
    max_image_bytes: int = 2 * 1024 * 1024
    max_resume_bytes: int = 5 * 1024 * 1024

    # Rate limiting: attempts per minute per client IP on sensitive auth endpoints.
    rate_limit_auth: int = 10

    # Outgoing email (optional). Without SMTP_HOST, development mode logs emails
    # (including reset links) to the server console instead of sending them.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "SkillAlign <no-reply@skillalign.local>"
    smtp_starttls: bool = True

    # Credentials live in the git-ignored project-root `.env` (the single place to edit).
    # `backend/.env` is still read for backward compatibility; the root file wins when both set a
    # value, and real environment variables override both.
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _check_secrets(self):
        if self.secret_key in INSECURE_SECRETS or len(self.secret_key) < 32:
            if self.app_env == "production":
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production")
            # Development/test fallback: a random per-process key. Tokens stop
            # working after a restart, so set SECRET_KEY in .env for convenience.
            self.secret_key = secrets.token_urlsafe(48)
            if self.app_env != "test":
                log.warning("SECRET_KEY is not set; using a temporary random key (sessions end on restart).")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production (serve the app over HTTPS)")
        return self

    @property
    def cors_origins(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.frontend_origins.split(",") if o.strip()]
        return list(dict.fromkeys([self.frontend_origin.rstrip("/"), *extra]))

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


settings = Settings()
