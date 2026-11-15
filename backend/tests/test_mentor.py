"""Phase 5: teacher profile, assignments, mentor scoping, mentoring notes."""

import pytest

from conftest import auth_headers, login, make_user, register, take_assessment

API = "/api/v1"


@pytest.fixture()
def world(client, db, admin):
    """Two mentors, three students: s1 and s2 assigned to mentor A, s3 to mentor B."""
    from app import models
    from app.models import UserRole

    make_user(db, "mentor.a@example.com", UserRole.teacher, name="Mentor A")
    make_user(db, "mentor.b@example.com", UserRole.teacher, name="Mentor B")
    for i in (1, 2, 3):
        register(client, email=f"s{i}@example.com", name=f"Student {i}")
    ids = {u.email: u.id for u in db.query(models.User)}

    def assign(student, mentor):
        r = client.post(f"{API}/admin/assignments", headers=admin,
                        json={"student_id": ids[student], "teacher_id": ids[mentor]})
        assert r.status_code == 201, r.text
        return r.json()

    a1 = assign("s1@example.com", "mentor.a@example.com")
    assign("s2@example.com", "mentor.a@example.com")
    assign("s3@example.com", "mentor.b@example.com")
    tok = lambda e: auth_headers(login(client, e).json()["access_token"])  # noqa: E731
    return {"ids": ids, "a": tok("mentor.a@example.com"), "b": tok("mentor.b@example.com"),
            "s1": tok("s1@example.com"), "s3": tok("s3@example.com"), "admin": admin, "a1": a1}


def test_teacher_profile(client, teacher):
    r = client.put(f"{API}/teachers/me/profile", headers=teacher, json={
        "full_name": "Dr  Priya Nair", "qualification": "PhD", "institution": "JSS", "designation": "Professor",
        "years_experience": 12, "areas_of_expertise": "Data science", "biography": " ",
    })
    assert r.status_code == 200
    p = r.json()
    assert p["full_name"] == "Dr Priya Nair" and p["years_experience"] == 12 and p["biography"] is None
    assert client.put(f"{API}/teachers/me/profile", headers=teacher,
                      json={"full_name": "X Y", "years_experience": 99}).status_code == 422


def test_teacher_profile_forbidden_for_students_and_admins(client, student, admin):
    assert client.get(f"{API}/teachers/me/profile", headers=student).status_code == 403
    assert client.get(f"{API}/teachers/me/profile", headers=admin).status_code == 403


def test_mentor_sees_only_assigned_students(client, world):
    names = [s["full_name"] for s in client.get(f"{API}/mentor/students", headers=world["a"]).json()]
    assert names == ["Student 1", "Student 2"]
    assert [s["full_name"] for s in client.get(f"{API}/mentor/students", headers=world["b"]).json()] == ["Student 3"]
    assert len(client.get(f"{API}/mentor/students", headers=world["admin"]).json()) == 3

    s3 = world["ids"]["s3@example.com"]
    assert client.get(f"{API}/mentor/students/{s3}", headers=world["a"]).status_code == 404  # not "403": no enumeration
    assert client.post(f"{API}/mentor/students/{s3}/notes", headers=world["a"], json={"note": "hi"}).status_code == 404
    s1 = world["ids"]["s1@example.com"]
    assert client.get(f"{API}/mentor/students/{s1}", headers=world["a"]).status_code == 200
    # A teacher id is not a student
    assert client.get(f"{API}/mentor/students/{world['ids']['mentor.b@example.com']}", headers=world["admin"]).status_code == 404


def test_search_and_faculty_summary_are_scoped(client, world):
    found = client.get(f"{API}/mentor/students", headers=world["a"], params={"search": "student 2"}).json()
    assert [s["full_name"] for s in found] == ["Student 2"]
    assert client.get(f"{API}/mentor/students", headers=world["a"], params={"search": "student 3"}).json() == []
    assert client.get(f"{API}/faculty/summary", headers=world["a"]).json()["students"] == 2
    assert client.get(f"{API}/faculty/summary", headers=world["admin"]).json()["students"] == 3


def test_mentor_dashboard_and_needs_attention(client, world, db):
    from app import models

    s1 = world["s1"]
    take_assessment(client, s1, db, "SQL", correct=0)  # 0%
    d = client.get(f"{API}/mentor/dashboard", headers=world["a"]).json()
    assert d["scope"] == "assigned students" and d["total_students"] == 2 and d["participating"] == 1
    assert d["average_score"] == 0.0
    reasons = {x["full_name"]: x["reasons"] for x in d["needs_attention"]}
    assert "Average score below 50%" in reasons["Student 1"]
    assert "No assessments taken yet" in reasons["Student 2"]
    assert "No target career selected" in reasons["Student 2"]


def test_student_detail_contents(client, world, db):
    from app import models

    s1 = world["s1"]
    cid = next(c["id"] for c in client.get(f"{API}/careers", headers=s1).json() if c["name"] == "Data Analyst")
    client.put(f"{API}/students/me/profile", headers=s1, json={"full_name": "Student 1", "college": "RVCE",
                                                                "target_career_id": cid,
                                                                "date_of_birth": "2002-05-01T00:00:00Z"})
    take_assessment(client, s1, db, "SQL")

    d = client.get(f"{API}/mentor/students/{world['ids']['s1@example.com']}", headers=world["a"]).json()
    assert d["profile"]["college"] == "RVCE" and "date_of_birth" not in d["profile"]
    assert d["gaps"]["career"] == "Data Analyst" and d["gaps"]["alignment_score"] == 17  # SQL 4/4*5 = 5 of 29
    assert d["skill_performance"] == [{"skill": "SQL", "attempts": 1, "best": 100.0, "latest": 100.0, "average": 100.0}]
    assert d["summary"]["target_career"]["alignment_score"] == 17


def test_notes_visibility_and_ownership(client, world):
    s1 = world["ids"]["s1@example.com"]
    rid = client.get(f"{API}/resources", headers=world["s1"]).json()[0]["id"]
    post = lambda h, body: client.post(f"{API}/mentor/students/{s1}/notes", headers=h, json=body)  # noqa: E731
    fb = post(world["a"], {"note": "Great SQL progress!", "note_type": "feedback"})
    assert fb.status_code == 201 and fb.json()["teacher_name"] == "Mentor A"
    rec = post(world["a"], {"note": "Try this", "note_type": "resource_recommendation", "resource_id": rid})
    assert rec.json()["resource"]["id"] == rid
    concern = post(world["a"], {"note": "Seems disengaged", "note_type": "concern", "visible_to_student": True})
    assert concern.json()["visible_to_student"] is False  # concerns are always private
    assert post(world["a"], {"note": "x", "note_type": "resource_recommendation"}).status_code == 422
    assert post(world["a"], {"note": "x", "resource_id": 999999}).status_code == 422
    assert post(world["a"], {"note": "   "}).status_code == 422

    mine = client.get(f"{API}/students/me/mentoring", headers=world["s1"]).json()
    assert [m["full_name"] for m in mine["mentors"]] == ["Mentor A"]
    assert {n["note"] for n in mine["notes"]} == {"Great SQL progress!", "Try this"}
    assert client.get(f"{API}/students/me/mentoring", headers=world["s3"]).json()["notes"] == []

    # Admin can add notes; mentor A cannot delete the admin's note, admin can delete any.
    admin_note = post(world["admin"], {"note": "Admin note"}).json()
    assert client.delete(f"{API}/mentor/notes/{admin_note['id']}", headers=world["a"]).status_code == 403
    assert client.delete(f"{API}/mentor/notes/{fb.json()['id']}", headers=world["b"]).status_code == 404
    assert client.delete(f"{API}/mentor/notes/{fb.json()['id']}", headers=world["a"]).status_code == 204
    assert client.delete(f"{API}/mentor/notes/{admin_note['id']}", headers=world["admin"]).status_code == 204


def test_assignment_end_and_reassign_keeps_history(client, world):
    admin, s1 = world["admin"], world["ids"]["s1@example.com"]
    a1 = world["a1"]
    assert client.post(f"{API}/admin/assignments", headers=admin,
                       json={"student_id": s1, "teacher_id": world["ids"]["mentor.a@example.com"]}).status_code == 409
    assert client.post(f"{API}/admin/assignments/{a1['id']}/end", headers=admin, json={"reason": "x"}).status_code == 422
    ended = client.post(f"{API}/admin/assignments/{a1['id']}/end", headers=admin, json={"reason": "Changed department"})
    assert ended.status_code == 200 and ended.json()["is_active"] is False and ended.json()["removed_at"]
    assert client.post(f"{API}/admin/assignments/{a1['id']}/end", headers=admin, json={"reason": "again"}).status_code == 400
    # Mentor A immediately loses access.
    assert client.get(f"{API}/mentor/students/{s1}", headers=world["a"]).status_code == 404
    # Reassign to B, then back to A: history keeps every row.
    for mentor in ("mentor.b@example.com", "mentor.a@example.com"):
        assert client.post(f"{API}/admin/assignments", headers=admin,
                           json={"student_id": s1, "teacher_id": world["ids"][mentor]}).status_code == 201
    hist = client.get(f"{API}/admin/assignments", headers=admin, params={"student_id": s1}).json()
    assert [(h["teacher_name"], h["is_active"]) for h in hist] == [("Mentor A", True), ("Mentor B", True), ("Mentor A", False)]
    assert hist[-1]["removal_reason"] == "Changed department"


def test_assignment_validation_and_permissions(client, world):
    ids, admin = world["ids"], world["admin"]
    bad = [(ids["s1@example.com"], ids["s2@example.com"]), (ids["mentor.a@example.com"], ids["mentor.b@example.com"]),
           (999999, ids["mentor.a@example.com"])]
    for s, t in bad:
        assert client.post(f"{API}/admin/assignments", headers=admin, json={"student_id": s, "teacher_id": t}).status_code == 422
    for h in (world["a"], world["s1"]):
        assert client.get(f"{API}/admin/assignments", headers=h).status_code == 403
        assert client.get(f"{API}/admin/users", headers=h).status_code == 403
    for h in (world["s1"],):
        assert client.get(f"{API}/mentor/students", headers=h).status_code == 403
        assert client.get(f"{API}/mentor/dashboard", headers=h).status_code == 403
    users = client.get(f"{API}/admin/users", headers=admin, params={"role": "teacher"}).json()
    assert {u["full_name"] for u in users} == {"Mentor A", "Mentor B"}
    assert client.get(f"{API}/admin/users", headers=admin, params={"role": "wizard"}).status_code == 422


def test_audit_records_assignments_and_notes(client, world, db):
    from app import models

    client.post(f"{API}/mentor/students/{world['ids']['s1@example.com']}/notes", headers=world["a"], json={"note": "hello"})
    actions = {a.action for a in db.query(models.AuditLog)}
    assert {"admin.assignment_created", "mentor.note_added"} <= actions
