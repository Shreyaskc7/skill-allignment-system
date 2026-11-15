"""Application configuration.

All secrets come from environment variables. The ``.env`` file is local-only and
must never be committed. See ``.env.example`` for the required names.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent Workforce Skill Alignment System"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/skill_alignment_db"
    frontend_origin: str = "http://localhost:5173"
    create_tables_on_start: bool = False

    # Security - all loaded from environment, never hardcoded.
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    refresh_secret: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    # Argon2id cost: time_cost is the number of passes (not PBKDF2-style
    # iterations), so keep it small. 3 passes / 64 MiB follows OWASP guidance.
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 4

    # Rate limiting (requests per minute on auth endpoints)
    rate_limit_auth: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()