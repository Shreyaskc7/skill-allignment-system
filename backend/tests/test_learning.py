"""Phase 9: verified resource catalogue, personalised learning path, progress and history."""

import json
import re

from app.services.learning import RESOURCE_FILE, RESOURCE_TYPES, target_difficulty

API = "/api/v1"


def _set_level(db, skill, level, email="student@example.com"):
    from app import models

    u = db.query(models.User).filter_by(email=email).one()
    s = db.query(models.Skill).filter_by(name=skill).one()
    db.add(models.StudentSkill(user_id=u.id, skill_id=s.id, level=level))
    db.commit()


def _target(client, h, name):
    cid = next(c["id"] for c in client.get(f"{API}/careers", headers=h).json() if c["name"] == name)
    client.put(f"{API}/students/me/target-career", headers=h, json={"target_career_id": cid})
    return cid


# ------------------------------------------------------------------ catalogue

def test_resource_file_covers_every_skill_with_valid_entries():
    from app.seed_data import CATALOG

    data = json.loads(RESOURCE_FILE.read_text(encoding="utf-8"))
    assert set(data["skills"]) == set(CATALOG)
    titles = set()
    for skill, rows in data["skills"].items():
        assert len(rows) >= 2, skill
        for r in rows:
            assert re.match(r"^https://\S+$", r["url"]), r["url"]
            assert r["type"] in RESOURCE_TYPES and r["difficulty"] in ("beginner", "intermediate", "advanced")
            assert (skill, r["title"]) not in titles
            titles.add((skill, r["title"]))
    assert data["verified_on"]


def test_resources_loaded_idempotently_and_v1_titles_kept(client, db):
    from app import models
    from app.services.learning import load_resources

    assert db.query(models.LearningResource).count() == 81
    assert load_resources(db) == 0
    assert db.query(models.LearningResource).filter_by(title="SQLBolt").count() == 1  # v1 resource


def test_resource_filters(client, student):
    get = lambda **p: client.get(f"{API}/resources", headers=student, params=p).json()  # noqa: E731
    assert {r["type"] for r in get(type="practice")} == {"practice"}
    assert {r["difficulty"] for r in get(difficulty="advanced")} == {"advanced"}
    assert all("MDN" in r["provider"] or "mdn" in r["title"].lower() for r in get(search="MDN"))
    rid = get()[0]["id"]
    client.post(f"{API}/progress/{rid}", headers=student, json={"status": "in_progress"})
    assert [r["id"] for r in get(status="in_progress")] == [rid]


# ------------------------------------------------------------------ path

def test_target_difficulty_rule():
    assert [target_difficulty(x) for x in (None, 1, 2, 3, 4, 5)] == [
        "beginner", "beginner", "beginner", "intermediate", "advanced", "advanced"]


def test_path_needs_a_target(client, student):
    assert client.get(f"{API}/learning/path", headers=student).status_code == 409


def test_path_orders_gaps_and_adapts_difficulty(client, student, db):
    _target(client, student, "Python Backend Developer")
    _set_level(db, "Python", 5)   # meets 4 -> done
    _set_level(db, "SQL", 3)      # needs 4 -> intermediate resources first
    p = client.get(f"{API}/learning/path", headers=student).json()
    assert p["career"] == "Python Backend Developer"
    assert [d["skill"] for d in p["completed_skills"]] == ["Python"]
    steps = {s["skill"]: s for s in p["steps"]}
    assert set(steps) == {"FastAPI", "SQL", "PostgreSQL", "Git", "Docker"}
    assert [s["step"] for s in p["steps"]] == list(range(1, 6))
    assert p["steps"][0]["gap_status"] == "critical"
    sql = steps["SQL"]
    assert sql["status"] == "todo" and sql["target_difficulty"] == "intermediate"
    assert sql["resources"][0]["difficulty"] == "intermediate"
    assert steps["FastAPI"]["status"] == "not_assessed" and steps["FastAPI"]["resources"][0]["difficulty"] == "beginner"
    assert all(1 <= len(s["resources"]) <= 3 for s in p["steps"])


def test_path_reacts_to_progress(client, student, db):
    _target(client, student, "Python Backend Developer")
    _set_level(db, "Git", 1)
    git = next(s for s in client.get(f"{API}/learning/path", headers=student).json()["steps"] if s["skill"] == "Git")
    first, rest = git["resources"][0], git["resources"][1:]
    client.post(f"{API}/progress/{first['id']}", headers=student, json={"status": "in_progress"})
    git = next(s for s in client.get(f"{API}/learning/path", headers=student).json()["steps"] if s["skill"] == "Git")
    assert git["status"] == "in_progress"
    for r in git["resources"]:
        client.post(f"{API}/progress/{r['id']}", headers=student, json={"status": "completed"})
    git = next(s for s in client.get(f"{API}/learning/path", headers=student).json()["steps"] if s["skill"] == "Git")
    assert git["status"] == "ready_to_reassess" and git["resources"] == [] and git["completed_resources"] == 3
    assert "reassess" in git["action"]
    assert rest  # Git has 3 resources in the catalogue


def test_explicit_career_and_errors(client, student):
    cid = _target(client, student, "Data Analyst")
    assert client.get(f"{API}/learning/path", headers=student, params={"career_id": cid}).json()["career"] == "Data Analyst"
    assert client.get(f"{API}/learning/path", headers=student, params={"career_id": 999999}).status_code == 404


# ------------------------------------------------------------------ progress and history

def test_progress_timestamps_notes_and_history(client, student):
    rid = client.get(f"{API}/resources", headers=student).json()[0]["id"]
    r1 = client.post(f"{API}/progress/{rid}", headers=student, json={"status": "in_progress", "notes": "  chapter 2  "}).json()
    assert r1["started_at"] and r1["completed_at"] is None and r1["notes"] == "chapter 2"
    r2 = client.post(f"{API}/progress/{rid}", headers=student, json={"status": "completed"}).json()
    assert r2["completed_at"] and r2["started_at"] == r1["started_at"] and r2["notes"] == "chapter 2"
    r3 = client.post(f"{API}/progress/{rid}", headers=student, json={"status": "completed", "notes": "done"}).json()
    assert r3["completed_at"] == r2["completed_at"]  # re-saving keeps the original completion time
    h = client.get(f"{API}/learning/history", headers=student).json()
    assert len(h) == 1 and h[0]["status"] == "completed" and h[0]["notes"] == "done"
    r4 = client.post(f"{API}/progress/{rid}", headers=student, json={"status": "not_started"}).json()
    assert r4["started_at"] is None and r4["completed_at"] is None
    assert client.get(f"{API}/learning/history", headers=student).json() == []


def test_progress_validation_and_permissions(client, student, teacher):
    rid = client.get(f"{API}/resources", headers=student).json()[0]["id"]
    assert client.post(f"{API}/progress/{rid}", headers=student, json={"status": "bogus"}).status_code == 422
    assert client.post(f"{API}/progress/{rid}", headers=student, json={"notes": "x" * 2001}).status_code == 422
    assert client.post(f"{API}/progress/999999", headers=student, json={"status": "completed"}).status_code == 404
    for path in ("/learning/path", "/learning/history"):
        assert client.get(API + path, headers=teacher).status_code == 403
        assert client.get(API + path).status_code == 401
    assert client.post(f"{API}/progress/{rid}", headers=teacher, json={"status": "completed"}).status_code == 403
