"""Version 1 features, now exercised through authenticated users."""

import io

from app import schemas  # noqa: F401  (EmailStr requires email-validator)
from app.security import hash_password, verify_password
from conftest import take_assessment


def test_password_hashing_round_trip():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)
    assert not verify_password("anything", "")
    assert not verify_password("anything", "not-a-hash")


def test_health_endpoints(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/db").json() == {"status": "ok", "database": "connected"}


def test_catalogue_seeded_and_no_demo_user(client, admin, db):
    from app import models

    careers = client.get("/api/v1/careers", headers=admin).json()
    assert len(careers) == 5
    summary = client.get("/api/v1/faculty/summary", headers=admin).json()
    assert summary["students"] == 0  # no hardcoded demo student any more
    assert summary["skills_catalogued"] == 26
    assert db.query(models.User).filter_by(email="student@skillalign.local").first() is None


def test_questions_do_not_expose_answers(client, student):
    skill_id = client.get("/api/v1/assessments/skills", headers=student).json()[0]["id"]
    attempt = client.post("/api/v1/assessments/attempts", headers=student, json={"skill_id": skill_id}).json()
    assert attempt["questions"]
    for q in attempt["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q


def test_gap_score_rises_after_perfect_assessment(client, student, db):
    from app import models

    careers = {c["name"]: c["id"] for c in client.get("/api/v1/careers", headers=student).json()}
    role_id = careers["Python Backend Developer"]
    before = client.get(f"/api/v1/gaps/{role_id}", headers=student).json()["alignment_score"]

    result = take_assessment(client, student, db, "Python")
    assert result["score_percent"] == 100
    assert result["estimated_level"] == 5

    after = client.get(f"/api/v1/gaps/{role_id}", headers=student).json()["alignment_score"]
    assert after > before


def test_csv_import_extracts_skills_and_skips_duplicates(client, teacher):
    csv_body = "title,description,company\nData Analyst,Needs SQL and Power BI and python,Acme\n"
    files = {"file": ("jobs.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    first = client.post("/api/v1/jobs/import-csv", headers=teacher, files=files).json()
    assert first["imported"] == 1
    assert {"SQL", "Power BI", "Python"} <= set(first["skills_found"])

    files = {"file": ("jobs.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    second = client.post("/api/v1/jobs/import-csv", headers=teacher, files=files).json()
    assert second == {**second, "imported": 0, "skipped": 1}


def test_resource_progress_status_round_trip(client, student):
    resources = client.get("/api/v1/resources", headers=student).json()
    assert {r["status"] for r in resources} == {"not_started"}
    rid = resources[0]["id"]
    assert client.post(f"/api/v1/progress/{rid}", headers=student, json={"status": "completed"}).status_code == 200
    assert client.post(f"/api/v1/progress/{rid}", headers=student, json={"status": "bogus"}).status_code == 422
    assert client.post("/api/v1/progress/999999", headers=student, json={"status": "completed"}).status_code == 404
    updated = {r["id"]: r["status"] for r in client.get("/api/v1/resources", headers=student).json()}
    assert updated[rid] == "completed"
    assert client.get("/api/v1/progress", headers=student).json()["resources"] == {
        "completed": 1, "in_progress": 0, "total_tracked": 1}


def test_assessment_history_records_attempts(client, student, db):
    take_assessment(client, student, db, "SQL", correct=0)
    history = client.get("/api/v1/assessments/history", headers=student).json()
    assert len(history) == 1 and history[0]["correct"] == 0


def test_csv_import_rejects_missing_columns(client, admin):
    files = {"file": ("bad.csv", io.BytesIO(b"name,text\nx,y\n"), "text/csv")}
    assert client.post("/api/v1/jobs/import-csv", headers=admin, files=files).status_code == 400
