"""Phase 11: N+1 regression guard. List endpoints must use a constant number of SQL statements."""

import io

import pytest
from sqlalchemy import event

from conftest import auth_headers, login, make_user

ENDPOINTS = [
    ("student", "/api/v1/jobs?page_size=100"), ("student", "/api/v1/students/me/dashboard"),
    ("student", "/api/v1/learning/path"), ("student", "/api/v1/careers/recommendations"),
    ("student", "/api/v1/resources"), ("student", "/api/v1/assessments/history"),
    ("admin", "/api/v1/mentor/students"), ("admin", "/api/v1/mentor/dashboard"),
    ("admin", "/api/v1/admin/accounts"), ("admin", "/api/v1/admin/assignments"),
    ("admin", "/api/v1/question-bank/questions?page_size=100"), ("admin", "/api/v1/admin/audit"),
    ("admin", "/api/v1/faculty/summary"), ("admin", "/api/v1/admin/stats"),
]


def _grow(client, db, admin, teacher, start, count):
    from app import models
    from app.models import UserRole

    da = db.query(models.CareerRole).filter_by(name="Data Analyst").one()
    sql = db.query(models.Skill).filter_by(name="SQL").one()
    for i in range(start, start + count):
        u = make_user(db, f"s{i}@example.com", UserRole.student, name=f"Student {i}")
        db.add(models.StudentProfile(user_id=u.id, target_career_id=da.id))
        db.add(models.StudentSkill(user_id=u.id, skill_id=sql.id, level=3))
        db.add(models.StudentTeacherAssignment(student_id=u.id, teacher_id=teacher.id, is_active=True))
        db.add(models.AssessmentAttempt(user_id=u.id, skill_id=sql.id, status="submitted", total_questions=5,
                                        correct_answers=3, score_percent=60))
    db.commit()
    csv = "title,description\n" + "".join(f"Job {i},SQL Python Excel role {i}\n" for i in range(start, start + count))
    client.post("/api/v1/jobs/import-csv", headers=admin, files={"file": ("j.csv", io.BytesIO(csv.encode()), "text/csv")})


def _measure(client, headers):
    from app.db import engine

    counts = {}
    n = {"q": 0}

    def count(*_a, **_k):
        n["q"] += 1

    event.listen(engine, "before_cursor_execute", count)
    try:
        for role, path in ENDPOINTS:
            n["q"] = 0
            assert client.get(path, headers=headers[role]).status_code == 200, path
            counts[path] = n["q"]
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return counts


@pytest.mark.slow
def test_list_endpoints_do_not_scale_queries_with_data(client, db, admin):
    from app import models
    from app.models import UserRole

    teacher = make_user(db, "t@example.com", UserRole.teacher)
    _grow(client, db, admin, teacher, 0, 3)
    stu = auth_headers(login(client, "s0@example.com").json()["access_token"])
    headers = {"student": stu, "admin": admin}
    small = _measure(client, headers)
    _grow(client, db, admin, teacher, 3, 9)  # four times the data
    large = _measure(client, headers)
    grown = {p: (small[p], large[p]) for p in small if large[p] - small[p] > 2}
    assert not grown, f"query count grows with data (N+1): {grown}"
    assert db.query(models.User).count() >= 14
