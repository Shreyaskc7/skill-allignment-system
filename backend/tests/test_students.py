"""Phase 4: student profile, uploads, self-reported skills, dashboard and access isolation."""

import io

import pytest

from conftest import auth_headers, login, register, take_assessment

API = "/api/v1/students/me"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def _profile_body(**over):
    return {"full_name": "Test Student", **over}


def _career_id(client, h, name="Python Backend Developer"):
    return next(c["id"] for c in client.get("/api/v1/careers", headers=h).json() if c["name"] == name)


def test_profile_created_at_registration_with_phone(client):
    register(client, phone="+91 90000 11111")
    h = auth_headers(login(client, "student@example.com").json()["access_token"])
    p = client.get(f"{API}/profile", headers=h).json()
    assert p["email"] == "student@example.com" and p["phone"] == "+91 90000 11111"
    assert 0 < p["completion"]["percent"] < 100
    assert "Target career" in p["completion"]["missing"]


def test_update_profile_and_completion(client, student):
    cid = _career_id(client, student)
    body = _profile_body(
        full_name="  Asha   Verma ", phone="+91 98450 12345", location="Bengaluru", college="RV College",
        degree="MCA", department="Computer Applications", specialization="Data Science", current_semester=3,
        graduation_year=2027, cgpa=8.4, career_interests="Backend APIs", preferred_locations="Bengaluru, Pune",
        experience_level="fresher", target_career_id=cid, technical_skills="  ",
    )
    r = client.put(f"{API}/profile", headers=student, json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["full_name"] == "Asha Verma" and p["technical_skills"] is None
    assert p["target_career_name"] == "Python Backend Developer"
    assert set(p["completion"]["missing"]) == {"Profile photo", "Skills and interests"}
    assert client.get("/api/v1/auth/me", headers=student).json()["full_name"] == "Asha Verma"


@pytest.mark.parametrize("field,value", [
    ("current_semester", 13), ("graduation_year", 1900), ("cgpa", 101), ("phone", "call me"),
    ("experience_level", "guru"), ("full_name", " "), ("target_career_id", 999999),
])
def test_profile_validation(client, student, field, value):
    assert client.put(f"{API}/profile", headers=student, json=_profile_body(**{field: value})).status_code == 422


def test_profile_cannot_set_file_paths_or_other_users(client, student, db):
    from app import models

    r = client.put(f"{API}/profile", headers=student,
                   json=_profile_body(profile_image_url="../../etc/passwd", resume_url="x", user_id=999))
    assert r.status_code == 200
    p = db.query(models.StudentProfile).one()
    assert p.profile_image_url is None and p.resume_url is None and p.user_id != 999


def test_photo_upload_download_replace_delete(client, student, isolated_uploads):
    files = {"file": ("me.png", io.BytesIO(PNG), "image/png")}
    r = client.post(f"{API}/photo", headers=student, files=files)
    assert r.status_code == 200 and r.json()["has_profile_image"]
    stored = list((isolated_uploads / "images").iterdir())
    assert len(stored) == 1 and stored[0].name != "me.png" and stored[0].suffix == ".png"

    d = client.get(f"{API}/photo", headers=student)
    assert d.status_code == 200 and d.content == PNG and d.headers["content-type"] == "image/png"
    assert d.headers["x-content-type-options"] == "nosniff"

    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    client.post(f"{API}/photo", headers=student, files={"file": ("x.jpg", io.BytesIO(jpg), "image/jpeg")})
    assert [p.suffix for p in (isolated_uploads / "images").iterdir()] == [".jpg"]  # old file removed

    assert client.delete(f"{API}/photo", headers=student).json()["has_profile_image"] is False
    assert list((isolated_uploads / "images").iterdir()) == []
    assert client.get(f"{API}/photo", headers=student).status_code == 404


@pytest.mark.parametrize("endpoint,content,name,ctype,status", [
    ("photo", b"<script>alert(1)</script>", "evil.png", "image/png", 415),   # extension lies
    ("photo", PDF, "doc.png", "image/png", 415),
    ("photo", b"", "empty.png", "image/png", 400),
    ("resume", PNG, "cv.pdf", "application/pdf", 415),
    ("resume", b"MZ\x90\x00 executable", "cv.pdf", "application/pdf", 415),
])
def test_upload_rejects_wrong_content(client, student, endpoint, content, name, ctype, status):
    r = client.post(f"{API}/{endpoint}", headers=student, files={"file": (name, io.BytesIO(content), ctype)})
    assert r.status_code == status


def test_upload_size_limit(client, student):
    big = PDF + b"0" * (5 * 1024 * 1024)  # just over the 5 MB resume limit
    r = client.post(f"{API}/resume", headers=student, files={"file": ("cv.pdf", io.BytesIO(big), "application/pdf")})
    assert r.status_code == 413
    ok = client.post(f"{API}/resume", headers=student, files={"file": ("cv.pdf", io.BytesIO(PDF), "application/pdf")})
    assert ok.status_code == 200 and ok.json()["has_resume"]


def test_self_skills_are_separate_from_assessed(client, student):
    skills = {s["name"]: s["id"] for s in client.get("/api/v1/skills", headers=student).json()}
    body = {"skills": [{"skill_id": skills["Python"], "level": 5}, {"skill_id": skills["Teamwork"], "level": 3}]}
    r = client.put(f"{API}/self-skills", headers=student, json=body)
    assert r.status_code == 200 and {s["skill_name"] for s in r.json()} == {"Python", "Teamwork"}

    # Claiming Python level 5 must not count as proven proficiency.
    cid = _career_id(client, student)
    assert client.get(f"/api/v1/gaps/{cid}", headers=student).json()["alignment_score"] == 0
    client.put(f"{API}/target-career", headers=student, json={"target_career_id": cid})
    dash = client.get(f"{API}/dashboard", headers=student).json()
    assert dash["assessed_skills"] == [] and dash["self_reported_skill_count"] == 2
    assert dash["target_career"]["alignment_score"] == 0

    dup = {"skills": [{"skill_id": skills["Python"], "level": 2}, {"skill_id": skills["Python"], "level": 3}]}
    assert client.put(f"{API}/self-skills", headers=student, json=dup).status_code == 422
    bad = {"skills": [{"skill_id": 999999, "level": 2}]}
    assert client.put(f"{API}/self-skills", headers=student, json=bad).status_code == 422
    lvl = {"skills": [{"skill_id": skills["Python"], "level": 6}]}
    assert client.put(f"{API}/self-skills", headers=student, json=lvl).status_code == 422
    assert client.put(f"{API}/self-skills", headers=student, json={"skills": []}).json() == []


def test_dashboard_reflects_real_activity(client, student, db):
    from app import models

    empty = client.get(f"{API}/dashboard", headers=student).json()
    assert empty["target_career"] is None and empty["assessments"]["count"] == 0
    assert empty["assessments"]["average_score"] is None and empty["recommended_resources"] == []
    assert empty["matching_jobs"]["available"] is False and empty["recent_activity"] == []

    cid = _career_id(client, student, "Data Analyst")
    client.put(f"{API}/target-career", headers=student, json={"target_career_id": cid})
    take_assessment(client, student, db, "SQL", count=5, correct=3)  # 3/5 = 60% -> level 4 (Phase 6 bands)

    d = client.get(f"{API}/dashboard", headers=student).json()
    tc = d["target_career"]
    assert tc["name"] == "Data Analyst"
    # Data Analyst weights: SQL(4,w5) Excel(4,4) Python(3,4) Statistics(4,5) Power BI(3,4) Data Analysis(4,5) Comm(3,2)
    # SQL level 4 -> 4/4*5 = 5 of 29 -> 17.2% -> 17
    assert tc["alignment_score"] == 17 == client.get(f"/api/v1/gaps/{cid}", headers=student).json()["alignment_score"]
    assert tc["skills_total"] == 7 and tc["skills_met"] == 1  # SQL level 4 meets the required 4
    assert tc["missing_skills"][0]["priority"] == "High"
    assert d["assessments"] == {**d["assessments"], "count": 1, "average_score": 60.0, "best_score": 60.0}
    assert [s["skill"] for s in d["assessed_skills"]] == ["SQL"]
    assert d["recommended_resources"] and all(r["status"] != "completed" for r in d["recommended_resources"])
    first = d["recommended_resources"][0]
    client.post(f"/api/v1/progress/{first['id']}", headers=student, json={"status": "completed"})
    d2 = client.get(f"{API}/dashboard", headers=student).json()
    assert first["id"] not in [r["id"] for r in d2["recommended_resources"]]
    assert d2["learning"] == {"completed": 1, "in_progress": 0, "tracked": 1}
    assert {a["type"] for a in d2["recent_activity"]} == {"assessment", "learning"}


def test_students_cannot_see_each_other(client, student):
    client.put(f"{API}/profile", headers=student, json=_profile_body(college="Secret College"))
    client.post(f"{API}/resume", headers=student, files={"file": ("cv.pdf", io.BytesIO(PDF), "application/pdf")})
    register(client, email="other@example.com")
    other = auth_headers(login(client, "other@example.com").json()["access_token"])
    p = client.get(f"{API}/profile", headers=other).json()
    assert p["email"] == "other@example.com" and p["college"] is None and not p["has_resume"]
    assert client.get(f"{API}/resume", headers=other).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("get", "/profile"), ("put", "/profile"), ("get", "/dashboard"), ("get", "/self-skills"), ("get", "/photo"),
])
def test_student_routes_reject_staff_and_anonymous(client, teacher, admin, method, path):
    for headers in (teacher, admin):
        assert getattr(client, method)(API + path, headers=headers, **({"json": {}} if method == "put" else {})).status_code == 403
    assert getattr(client, method)(API + path).status_code == 401


def test_upload_path_traversal_is_never_served(client, student, db, isolated_uploads):
    from app import models

    client.get(f"{API}/profile", headers=student)
    (isolated_uploads.parent / "secret.txt").write_text("top secret")
    p = db.query(models.StudentProfile).one()
    p.resume_url = "../secret.txt"
    db.commit()
    assert client.get(f"{API}/resume", headers=student).status_code == 404
