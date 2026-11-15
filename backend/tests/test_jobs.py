"""Phase 8: extraction rules, job import/entry, search, and student-to-job matching."""

import io
import sys
from pathlib import Path

import pytest

from app.services.skill_extraction import DictionaryExtractor, default_terms

API = "/api/v1"
EXT = DictionaryExtractor(default_terms())


def _x(text):
    return {e.skill: e.required for e in EXT.extract(text)}


# ------------------------------------------------------------------ extractor rules (no database)

@pytest.mark.parametrize("text,expected", [
    ("Python, FastAPI and PostgreSQL. Docker is a plus.", {"Python": True, "FastAPI": True, "PostgreSQL": True, "Docker": False}),
    ("Postgres and MS Excel; ReactJS frontend", {"PostgreSQL": True, "Excel": True, "React": True}),
    ("No Java experience required. Strong SQL.", {"SQL": True}),
    ("You will excel in a team; collaboration matters.", {"Teamwork": True}),
    ("Knowledge of data analysis and data analytics", {"Data Analysis": True}),
    ("XML and HTML templates", {"HTML": True}),
    ("JavaScript developer", {"JavaScript": True}),
    ("Java developer", {"Java": True}),
    ("Git required. Git preferred later.", {"Git": True}),  # required wins over optional
    ("Python is preferred.", {"Python": False}),
])
def test_extractor_rules(text, expected):
    assert _x(text) == expected


def test_extractor_beats_v1_baseline_on_both_sets():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from evaluate_extractor import evaluate

    dev, held = evaluate("development"), evaluate("heldout")
    for r in (dev, held):
        assert r["current"]["f1"] > r["v1_baseline"]["f1"]
    # Regression floor on the blind held-out set (measured 0.918 when written).
    assert held["current"]["f1"] >= 0.90 and held["current"]["precision"] >= 0.90


# ------------------------------------------------------------------ import and manual entry

CSV = """title,company,location,description,posted_date,employment_type,experience,salary_min,salary_max,salary_currency,application_url,skills
Python Developer,Acme,Pune,"Python and SQL required. Docker is a plus.",2026-10-01,full-time,0-2,400000,700000,INR,https://acme.example/jobs/1,
Data Analyst,Beta,Bengaluru,"Excel, Power BI and statistics.",15/09/2026,internship,fresher,,,,,SQL;Excel;Klingon
Python Developer,Acme,Pune,"Python and SQL required. Docker is a plus.",2026-10-01,,,,,,,
,Gamma,Delhi,missing title,,,,,,,,
Bad Row,Delta,Delhi,"Needs Java.",yesterday,,,abc,,,ftp://x,
"""


def _import(client, headers, body=CSV, name="jobs.csv"):
    return client.post(f"{API}/jobs/import-csv", headers=headers,
                       files={"file": (name, io.BytesIO(body.encode()), "text/csv")})


def test_csv_import_validates_rows_and_reports(client, teacher):
    r = _import(client, teacher).json()
    assert r["imported"] == 2 and r["skipped"] == 3
    errs = {e["row"]: e["message"] for e in r["errors"]}
    assert "title and description are required" in errs[5]
    assert "salary_min must be a whole number" in errs[6] and "application_url" in errs[6]
    warns = " | ".join(w["message"] for w in r["warnings"])
    assert "duplicate" in warns and "unknown skill 'Klingon'" in warns
    jobs = {j["title"]: j for j in client.get(f"{API}/jobs", headers=teacher).json()["items"]}
    py = jobs["Python Developer"]
    assert (py["experience_min_years"], py["experience_max_years"], py["salary_min"], py["posted_on"]) == (0, 2, 400000, "2026-10-01")
    assert set(py["skills"]) == {"Python", "SQL", "Docker"}
    da = jobs["Data Analyst"]
    assert da["posted_on"] == "2026-09-15" and set(da["skills"]) == {"SQL", "Excel"}  # explicit skills column wins
    assert _import(client, teacher).json()["imported"] == 0  # whole file again: all duplicates


def test_csv_limits(client, teacher):
    assert _import(client, teacher, name="x.txt").status_code == 400
    assert _import(client, teacher, body="foo,bar\n1,2\n").status_code == 400
    big = "title,description\n" + ("T,D\n" * 600000)
    assert _import(client, teacher, body=big).status_code == 413


def test_manual_entry_with_explicit_or_extracted_skills(client, teacher, db):
    from app import models

    skills = {s.name: s.id for s in db.query(models.Skill)}
    body = {"title": "React Intern", "company": "Zeta", "location": "Remote", "employment_type": "internship",
            "description": "Build UIs with React and JavaScript. Git is a plus.", "application_url": "https://zeta.example"}
    r = client.post(f"{API}/jobs", headers=teacher, json=body)
    assert r.status_code == 201
    j = r.json()
    assert set(j["missing_skills"]) == {"React", "JavaScript"} and j["additional_skills"] == ["Git"]
    assert client.post(f"{API}/jobs", headers=teacher, json=body).status_code == 409
    manual = {**body, "title": "UI Intern", "skills": [{"skill_id": skills["CSS"], "required": True}]}
    assert client.post(f"{API}/jobs", headers=teacher, json=manual).json()["skills"] == ["CSS"]
    for bad in ({"application_url": "javascript:alert(1)"}, {"salary_min": 9, "salary_max": 1},
                {"employment_type": "forever"}, {"description": "short"}):
        assert client.post(f"{API}/jobs", headers=teacher, json={**body, "title": "X Y", **bad}).status_code == 422


def test_students_cannot_create_or_import(client, student):
    assert client.post(f"{API}/jobs", headers=student, json={}).status_code == 403
    assert _import(client, student).status_code == 403


# ------------------------------------------------------------------ matching

def _set(db, skill, level, email="student@example.com"):
    from app import models

    u = db.query(models.User).filter_by(email=email).one()
    s = db.query(models.Skill).filter_by(name=skill).one()
    db.add(models.StudentSkill(user_id=u.id, skill_id=s.id, level=level))
    db.commit()


def test_match_percent_rule(client, teacher, student, db):
    _import(client, teacher)
    _set(db, "Python", 4)   # >= 3: counts
    _set(db, "SQL", 2)      # < 3: does not count
    jobs = {j["title"]: j for j in client.get(f"{API}/jobs", headers=student).json()["items"]}
    py = jobs["Python Developer"]
    assert py["match_percent"] == 50  # 1 of 2 required (Docker is optional)
    assert py["matching_skills"] == ["Python"] and py["missing_skills"] == ["SQL"] and py["additional_skills"] == ["Docker"]
    assert jobs["Data Analyst"]["match_percent"] == 0
    detail = client.get(f"{API}/jobs/{py['id']}", headers=student).json()
    assert "description" in detail and "3/5" in detail["match_rule"]
    sql = next(x for x in detail["required"] if x["skill"] == "SQL")
    assert sql == {**sql, "your_level": 2, "has": False}


def test_job_without_skills_has_no_score(client, teacher, student):
    client.post(f"{API}/jobs", headers=teacher, json={
        "title": "Office Assistant", "description": "Filing, scheduling and front desk duties for our office."})
    j = client.get(f"{API}/jobs", headers=student, params={"search": "office"}).json()["items"][0]
    assert j["match_percent"] is None and j["skills"] == []


def test_search_filters_sort_and_pagination(client, teacher, student, db):
    _import(client, teacher)
    _set(db, "Excel", 5)
    _set(db, "SQL", 3)
    get = lambda **p: client.get(f"{API}/jobs", headers=student, params=p).json()  # noqa: E731
    assert [j["title"] for j in get(search="acme")["items"]] == ["Python Developer"]
    assert [j["title"] for j in get(location="bengal")["items"]] == ["Data Analyst"]
    excel = db.query(__import__("app.models", fromlist=["Skill"]).Skill).filter_by(name="Excel").one().id
    assert [j["title"] for j in get(skill_id=excel)["items"]] == ["Data Analyst"]
    assert [j["title"] for j in get(sort="relevance")["items"]] == ["Data Analyst", "Python Developer"]  # 100% vs 50%
    assert [j["title"] for j in get(sort="date")["items"]] == ["Python Developer", "Data Analyst"]
    assert [j["title"] for j in get(min_match=60)["items"]] == ["Data Analyst"]
    page = get(page_size=1, page=2)
    assert page["total"] == 2 and page["total_pages"] == 2 and len(page["items"]) == 1


def test_inactive_jobs_hidden_from_students(client, teacher, student):
    _import(client, teacher)
    jid = client.get(f"{API}/jobs", headers=teacher).json()["items"][0]["id"]
    full = client.get(f"{API}/jobs/{jid}", headers=teacher).json()
    body = {k: full[k] for k in ("title", "company", "location", "description")} | {"is_active": False}
    assert client.put(f"{API}/jobs/{jid}", headers=teacher, json=body).status_code == 200
    assert client.get(f"{API}/jobs/{jid}", headers=student).status_code == 404
    assert jid not in [j["id"] for j in client.get(f"{API}/jobs", headers=student).json()["items"]]
    assert jid in [j["id"] for j in client.get(f"{API}/jobs", headers=teacher, params={"include_inactive": True}).json()["items"]]


def test_dashboard_shows_top_matches(client, teacher, student, db):
    _import(client, teacher)
    _set(db, "Excel", 5)
    _set(db, "SQL", 5)
    top = client.get(f"{API}/students/me/dashboard", headers=student).json()["matching_jobs"]["top"]
    assert top[0]["title"] == "Data Analyst" and top[0]["match_percent"] == 100
