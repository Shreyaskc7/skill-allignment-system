"""Smoke tests for the current (pre-auth) API on a fresh database."""

import io

from app import schemas  # noqa: F401  (EmailStr requires email-validator)
from app.security import hash_password, verify_password


def test_password_hashing_round_trip():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_health_endpoints(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/db").json() == {"status": "ok", "database": "connected"}


def test_seed_on_fresh_database(client):
    careers = client.get("/api/v1/careers").json()
    assert len(careers) == 5
    summary = client.get("/api/v1/faculty/summary").json()
    assert summary["students"] == 1
    assert summary["skills_catalogued"] == 26


def test_questions_do_not_expose_answers(client):
    skill_id = client.get("/api/v1/assessments/skills").json()[0]["id"]
    questions = client.get(f"/api/v1/assessments/questions/{skill_id}").json()
    assert questions
    for q in questions:
        assert "correct_option" not in q
        assert "explanation" not in q


def test_gap_score_rises_after_perfect_assessment(client):
    careers = {c["name"]: c["id"] for c in client.get("/api/v1/careers").json()}
    role_id = careers["Python Backend Developer"]
    before = client.get(f"/api/v1/gaps/{role_id}").json()["alignment_score"]

    python_id = next(s["id"] for s in client.get("/api/v1/assessments/skills").json() if s["name"] == "Python")
    questions = client.get(f"/api/v1/assessments/questions/{python_id}").json()
    # Look up the answers server-side, as a test-only shortcut.
    from app.db import SessionLocal
    from app import models

    with SessionLocal() as db:
        answers = {str(q["id"]): db.get(models.AssessmentQuestion, q["id"]).correct_option for q in questions}
    result = client.post("/api/v1/assessments/submit", json={"skill_id": python_id, "answers": answers}).json()
    assert result["score_percent"] == 100
    assert result["estimated_level"] == 5

    after = client.get(f"/api/v1/gaps/{role_id}").json()["alignment_score"]
    assert after > before


def test_csv_import_extracts_skills_and_skips_duplicates(client):
    csv_body = "title,description,company\nData Analyst,Needs SQL and Power BI and python,Acme\n"
    files = {"file": ("jobs.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    first = client.post("/api/v1/jobs/import-csv", files=files).json()
    assert first["imported"] == 1
    assert {"SQL", "Power BI", "Python"} <= set(first["skills_found"])

    files = {"file": ("jobs.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    second = client.post("/api/v1/jobs/import-csv", files=files).json()
    assert second == {**second, "imported": 0, "skipped": 1}


def test_csv_import_rejects_missing_columns(client):
    files = {"file": ("bad.csv", io.BytesIO(b"name,text\nx,y\n"), "text/csv")}
    assert client.post("/api/v1/jobs/import-csv", files=files).status_code == 400
