"""Phase 7: explainable skill gaps and rule-based career recommendations."""

import pytest

from conftest import take_assessment

API = "/api/v1"


def _career(client, h, name):
    return next(c["id"] for c in client.get(f"{API}/careers", headers=h).json() if c["name"] == name)


def _set_level(db, email, skill_name, level):
    """Directly place an assessed level (test shortcut for exact hand calculations)."""
    from app import models

    user = db.query(models.User).filter_by(email=email).one()
    skill = db.query(models.Skill).filter_by(name=skill_name).one()
    db.add(models.StudentSkill(user_id=user.id, skill_id=skill.id, level=level, source="assessment"))
    db.commit()


def test_gap_analysis_explains_unchanged_score(client, student, db):
    # Python Backend Developer: Python(4,w5) FastAPI(3,4) SQL(4,4) PostgreSQL(3,4) Git(3,3) Docker(2,2); Σw = 22
    _set_level(db, "student@example.com", "Python", 5)   # capped 4/4*5 = 5.00
    _set_level(db, "student@example.com", "SQL", 2)      # 2/4*4  = 2.00
    _set_level(db, "student@example.com", "Docker", 1)   # 1/2*2  = 1.00
    g = client.get(f"{API}/gaps/{_career(client, student, 'Python Backend Developer')}", headers=student).json()
    assert g["alignment_score"] == 36  # 8 / 22 = 36.4%  (same weighted formula as version 1)
    by = {s["skill"]: s for s in g["skills"]}
    assert by["Python"]["contribution"] == 22.7 and by["Python"]["max_contribution"] == 22.7
    assert by["SQL"]["contribution"] == 9.1 and by["Docker"]["contribution"] == 4.5
    assert round(sum(s["contribution"] for s in g["skills"])) == g["alignment_score"]
    assert by["Python"]["status"] == "meets"
    assert by["SQL"]["status"] == "critical"            # gap 2, weight 4
    assert by["Docker"]["status"] == "needs_improvement"
    assert by["FastAPI"]["assessed"] is False and by["FastAPI"]["status"] == "critical"
    # critical = gap >= 2 and weight >= 4: SQL, FastAPI, PostgreSQL. Git (w3) and Docker (gap 1) need improvement.
    assert g["summary"] == {"meets": 1, "needs_improvement": 2, "critical": 3, "unassessed": 3, "total": 6}
    assert [s["status"] for s in g["skills"]] == ["critical"] * 3 + ["needs_improvement"] * 2 + ["meets"]
    assert "Σ" in g["formula"]


def test_next_steps_assess_first_then_learn(client, student, db):
    _set_level(db, "student@example.com", "SQL", 2)
    g = client.get(f"{API}/gaps/{_career(client, student, 'Data Analyst')}", headers=student).json()
    steps = g["next_steps"]
    assert 1 <= len(steps) <= 4
    sql = next(s for s in steps if s.get("skill") == "SQL")
    assert sql["type"] == "learn" and sql["resource"] is not None  # SQL has seeded resources
    assert any(s["type"] == "assess" for s in steps)


def test_self_reported_skills_shown_but_not_counted(client, student):
    skills = {s["name"]: s["id"] for s in client.get(f"{API}/skills", headers=student).json()}
    client.put(f"{API}/students/me/self-skills", headers=student,
               json={"skills": [{"skill_id": skills["Java"], "level": 5}]})
    g = client.get(f"{API}/gaps/{_career(client, student, 'Software Developer')}", headers=student).json()
    java = next(s for s in g["skills"] if s["skill"] == "Java")
    assert java["self_reported_level"] == 5 and java["current_level"] == 0 and not java["assessed"]
    assert g["alignment_score"] == 0


def test_evidence_links_to_attempt(client, student, db):
    r = take_assessment(client, student, db, "Git", count=5)
    g = client.get(f"{API}/gaps/{_career(client, student, 'Software Developer')}", headers=student).json()
    git = next(s for s in g["skills"] if s["skill"] == "Git")
    assert git["evidence_attempt_id"] == r["attempt_id"] and git["last_assessed_at"]


def test_recommendations_ranked_by_alignment(client, student, db):
    for skill, lvl in [("HTML", 4), ("CSS", 4), ("JavaScript", 5), ("React", 3)]:
        _set_level(db, "student@example.com", skill, lvl)
    rec = client.get(f"{API}/careers/recommendations", headers=student).json()
    names = [r["career"] for r in rec["recommendations"]]
    assert names[0] == "Frontend Developer" and len(names) == 5
    top = rec["recommendations"][0]
    # HTML 4/4*4 + CSS 4/4*4 + JS 4/4*5 + React 3/4*5 = 4+4+5+3.75 = 16.75 of Σw 23 -> 72.8% -> 73
    assert top["alignment_score"] == 73 and top["rank"] == 1
    assert set(top["matching_skills"]) == {"HTML", "CSS", "JavaScript"}
    assert top["skills_to_improve"] == ["React"] and set(top["missing_skills"]) == {"Git", "Communication"}
    assert [r["alignment_score"] for r in rec["recommendations"]] == sorted(
        (r["alignment_score"] for r in rec["recommendations"]), reverse=True)
    assert "not a prediction" in rec["method"]


def test_interests_break_ties_but_never_change_scores(client, student):
    rec0 = client.get(f"{API}/careers/recommendations", headers=student).json()["recommendations"]
    assert {r["alignment_score"] for r in rec0} == {0}  # nothing assessed: all tied
    client.put(f"{API}/students/me/profile", headers=student,
               json={"full_name": "Test Student", "career_interests": "machine learning and statistics",
                     "target_career_id": _career(client, student, "Data Analyst")})
    rec = client.get(f"{API}/careers/recommendations", headers=student).json()["recommendations"]
    assert rec[0]["career"] == "Machine Learning Engineer" and rec[0]["alignment_score"] == 0
    assert "machine" in rec[0]["interest_match"] and any("interests" in x for x in rec[0]["reasons"])
    assert next(r for r in rec if r["career"] == "Data Analyst")["is_target"] is True


def test_staff_and_anonymous_cannot_use_student_career_endpoints(client, teacher):
    assert client.get(f"{API}/careers/recommendations", headers=teacher).status_code == 403
    assert client.get(f"{API}/careers/recommendations").status_code == 401
    assert client.get(f"{API}/gaps/1", headers=teacher).status_code == 403


@pytest.mark.parametrize("career_id", [999999])
def test_unknown_career(client, student, career_id):
    assert client.get(f"{API}/gaps/{career_id}", headers=student).status_code == 404
