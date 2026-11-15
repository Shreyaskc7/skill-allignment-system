"""Database engine, session factory and helpers."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    if settings.database_url.startswith("sqlite"):
        # Used only for local experiments/tests; PostgreSQL is the supported database.
        return create_engine(settings.database_url, connect_args={"check_same_thread": False})
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return True if the database is reachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def create_all():
    """Create all missing tables. Safe to run on an existing database."""
    Base.metadata.create_all(bind=engine)