"""Programmatic access to Alembic: schema status checks and upgrades."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    if database_url:
        cfg.attributes["database_url"] = database_url
    return cfg


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


class SchemaOutOfDate(RuntimeError):
    pass


def ensure_schema_current(engine: Engine) -> None:
    current, head = current_revision(engine), head_revision()
    if current != head:
        raise SchemaOutOfDate(
            f"Database schema is at revision {current or 'none (not managed by Alembic yet)'}, "
            f"but the application needs {head}.\n"
            "Back up the database, then run from the backend directory:\n"
            "    alembic upgrade head\n"
            "(See DEVELOPMENT_PLAN.md / README for the backup command.)"
        )
