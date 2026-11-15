"""Test configuration.

Tests run ONLY against the database in TEST_DATABASE_URL and never against the
developer's real DATABASE_URL. The test database is wiped and rebuilt with
Alembic migrations for every test that uses it, so point it at a throwaway
database (CI uses a disposable PostgreSQL service container).
"""

import os

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# Must be set before any `app` module is imported (settings are read at import time).
os.environ["APP_ENV"] = "test"
os.environ["CREATE_TABLES_ON_START"] = "false"
os.environ["AUTO_MIGRATE"] = "false"
os.environ["ARGON2_TIME_COST"] = "1"  # fast hashing in tests only
os.environ["ARGON2_MEMORY_COST_KIB"] = "8192"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
os.environ["RATE_LIMIT_AUTH"] = "1000"  # the rate-limit test lowers this explicitly
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "sqlite://"

DB_FIXTURES = {"client", "engine_clean", "db"}

PASSWORD = "Passw0rd!"


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set; refusing to touch a real database")
    for item in items:
        if DB_FIXTURES & set(item.fixturenames):
            item.add_marker(skip)


def wipe_database(engine) -> None:
    """Remove every table, type and the alembic_version marker from the TEST database."""
    from sqlalchemy import MetaData, text

    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        else:
            md = MetaData()
            md.reflect(conn)
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            md.drop_all(conn)


@pytest.fixture()
def engine_clean():
    """An empty test database (no tables, not migrated)."""
    from app.db import engine

    wipe_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(engine_clean):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.migrations import upgrade_to_head
    from app.services import email, rate_limit

    upgrade_to_head(TEST_DATABASE_URL)
    rate_limit.reset()
    email.OUTBOX.clear()
    with TestClient(app) as c:  # startup: schema check + catalogue seed
        yield c


@pytest.fixture()
def db(client):
    from app.db import SessionLocal

    with SessionLocal() as s:
        yield s


# ------------------------------------------------------------------ helpers

def register(client, email="student@example.com", name="Test Student", password=PASSWORD, **extra):
    body = {"email": email, "full_name": name, "password": password, "confirm_password": password,
            "terms_accepted": True, **extra}
    return client.post("/api/v1/auth/register", json=body)


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user(db, email, role, password=PASSWORD, name="Staff Member", active=True):
    from app import models
    from app.security import hash_password

    u = models.User(email=email, full_name=name, role=role, password_hash=hash_password(password),
                    is_active=active, is_verified=True)
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def student(client):
    """Headers for a freshly registered, logged-in student."""
    assert register(client).status_code == 201
    return auth_headers(login(client, "student@example.com").json()["access_token"])


@pytest.fixture()
def teacher(client, db):
    from app.models import UserRole

    make_user(db, "teacher@example.com", UserRole.teacher)
    return auth_headers(login(client, "teacher@example.com").json()["access_token"])


@pytest.fixture()
def admin(client, db):
    from app.models import UserRole

    make_user(db, "admin@example.com", UserRole.admin)
    return auth_headers(login(client, "admin@example.com").json()["access_token"])


def take_assessment(client, headers, db, skill_name, count=5, correct=None):
    """Start an attempt for `skill_name` and submit it with `correct` right answers (default: all)."""
    from app import models

    skill = next(s for s in client.get("/api/v1/assessments/skills", headers=headers).json() if s["name"] == skill_name)
    a = client.post("/api/v1/assessments/attempts", headers=headers,
                    json={"skill_id": skill["id"], "question_count": count, "restart": True}).json()
    key = {q.question_id: q.correct_option for q in
           db.query(models.AssessmentAttemptQuestion).filter_by(attempt_id=a["attempt_id"]).order_by(
               models.AssessmentAttemptQuestion.position)}
    correct = count if correct is None else correct
    answers = [{"question_id": qid, "answer": right if i < correct else ("B" if right == "A" else "A")}
               for i, (qid, right) in enumerate(key.items())]
    r = client.post(f"/api/v1/assessments/attempts/{a['attempt_id']}/submit", headers=headers, json={"answers": answers})
    assert r.status_code == 200, r.text
    return r.json()
