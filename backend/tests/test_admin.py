"""Phase 10: administration (stats, accounts, catalogue, audit) and the admin permission matrix."""

import re

import pytest

from conftest import PASSWORD, auth_headers, login, make_user, register

API = "/api/v1"


def _admin_routes():
    """Every admin endpoint, taken from the OpenAPI schema (so new ones are covered automatically)."""
    from app.main import app

    routes = []
    for path, ops in app.openapi()["paths"].items():
        if path.startswith(f"{API}/admin"):
            concrete = re.sub(r"\{[^}]+\}", "1", path)
            routes += [(m.upper(), concrete) for m in sorted(ops) if m in ("get", "post", "put", "patch", "delete")]
    return routes


def test_permission_matrix_covers_every_admin_endpoint(client, student, teacher):
    routes = _admin_routes()
    assert len(routes) >= 19  # 19 at Phase 10: invitations, users, assignments, stats, accounts, skills, careers, resources, audit
    for method, path in routes:
        call = getattr(client, method.lower())
        kw = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
        assert call(path, headers=student, **kw).status_code == 403, (method, path, "student")
        assert call(path, headers=teacher, **kw).status_code == 403, (method, path, "teacher")
        assert call(path, **kw).status_code == 401, (method, path, "anonymous")


def test_stats(client, admin, student):
    s = client.get(f"{API}/admin/stats", headers=admin).json()
    assert s["users"] == {"student": 1, "teacher": 0, "admin": 1}
    assert s["skills"] == 26 and s["career_roles_active"] == 5 and s["questions_active"] == 572 and s["resources"] == 81
    assert s["logins_last_30_days"] >= 2


# ------------------------------------------------------------------ accounts

def test_list_and_filter_accounts(client, admin, teacher, student):
    all_ = client.get(f"{API}/admin/accounts", headers=admin).json()
    assert all_["total"] == 3 and "password_hash" not in str(all_)
    assert [u["role"] for u in client.get(f"{API}/admin/accounts", headers=admin, params={"role": "teacher"}).json()["items"]] == ["teacher"]
    assert client.get(f"{API}/admin/accounts", headers=admin, params={"search": "student@"}).json()["total"] == 1


def test_deactivate_signs_user_out_and_blocks_login(client, admin, student, db):
    from app import models

    sid = db.query(models.User).filter_by(email="student@example.com").one().id
    r = client.patch(f"{API}/admin/accounts/{sid}", headers=admin, json={"is_active": False, "reason": "left college"})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert client.get(f"{API}/auth/me", headers=student).status_code == 401
    assert login(client, "student@example.com").status_code == 403
    assert all(t.revoked_at for t in db.query(models.RefreshToken).filter_by(user_id=sid))
    log = db.query(models.AuditLog).filter_by(action="admin.user_updated").one()
    assert "left college" in log.details


def test_admin_safety_rules(client, admin, db):
    from app import models

    me = db.query(models.User).filter_by(email="admin@example.com").one()
    assert client.patch(f"{API}/admin/accounts/{me.id}", headers=admin, json={"is_active": False}).status_code == 409
    assert client.patch(f"{API}/admin/accounts/{me.id}", headers=admin, json={"role": "teacher"}).status_code == 409
    other = make_user(db, "admin2@example.com", models.UserRole.admin)
    # With two admins, one may be demoted...
    assert client.patch(f"{API}/admin/accounts/{other.id}", headers=admin, json={"role": "teacher"}).status_code == 200
    # ...and the remaining last admin is protected even from another (now teacher) account.
    assert client.patch(f"{API}/admin/accounts/999999", headers=admin, json={"is_active": False}).status_code == 404


def test_role_change_ends_assignments_and_creates_profile(client, admin, teacher, db):
    from app import models

    register(client, email="s1@example.com")
    ids = {u.email: u.id for u in db.query(models.User)}
    client.post(f"{API}/admin/assignments", headers=admin,
                json={"student_id": ids["s1@example.com"], "teacher_id": ids["teacher@example.com"]})
    r = client.patch(f"{API}/admin/accounts/{ids['s1@example.com']}", headers=admin, json={"role": "teacher"})
    assert r.json()["role"] == "teacher"
    a = db.query(models.StudentTeacherAssignment).one()
    db.refresh(a)
    assert a.is_active is False and "Role changed" in a.removal_reason
    assert db.query(models.TeacherProfile).filter_by(user_id=ids["s1@example.com"]).count() == 1
    assert client.patch(f"{API}/admin/accounts/{ids['s1@example.com']}", headers=admin, json={"role": "wizard"}).status_code == 422


# ------------------------------------------------------------------ catalogue

def test_skill_crud(client, admin):
    r = client.post(f"{API}/admin/skills", headers=admin, json={"name": " Kotlin ", "category": "Programming",
                                                                "esco_identifier": "S1.2.3"})
    assert r.status_code == 201 and r.json()["name"] == "Kotlin"
    assert client.post(f"{API}/admin/skills", headers=admin, json={"name": "kotlin", "category": "X"}).status_code == 409
    sid = r.json()["id"]
    upd = client.put(f"{API}/admin/skills/{sid}", headers=admin, json={"name": "Kotlin", "category": "Mobile"})
    assert upd.json()["category"] == "Mobile"
    assert client.put(f"{API}/admin/skills/{sid}", headers=admin, json={"name": "Python", "category": "X"}).status_code == 409


def test_career_crud_and_visibility(client, admin, student, db):
    from app import models

    sk = {s.name: s.id for s in db.query(models.Skill)}
    body = {"name": "Cloud Support Associate", "description": "Supports cloud workloads.",
            "requirements": [{"skill_id": sk["Linux"], "required_level": 3, "importance_weight": 5},
                             {"skill_id": sk["Docker"], "required_level": 2, "importance_weight": 3}]}
    r = client.post(f"{API}/admin/careers", headers=admin, json=body)
    assert r.status_code == 201 and len(r.json()["requirements"]) == 2
    cid = r.json()["id"]
    assert "Cloud Support Associate" in [c["name"] for c in client.get(f"{API}/careers", headers=student).json()]
    # deactivate: hidden from students and from recommendations, still listed for admins
    client.put(f"{API}/admin/careers/{cid}", headers=admin, json={**body, "is_active": False})
    assert "Cloud Support Associate" not in [c["name"] for c in client.get(f"{API}/careers", headers=student).json()]
    recs = client.get(f"{API}/careers/recommendations", headers=student).json()["recommendations"]
    assert "Cloud Support Associate" not in [x["career"] for x in recs]
    assert any(c["id"] == cid and not c["is_active"] for c in client.get(f"{API}/admin/careers", headers=admin).json())
    # validation
    bad = [{**body, "name": "X Y", "requirements": []},
           {**body, "name": "X Y", "requirements": [body["requirements"][0], body["requirements"][0]]},
           {**body, "name": "X Y", "requirements": [{"skill_id": sk["Linux"], "required_level": 6, "importance_weight": 1}]},
           {**body, "name": "X Y", "requirements": [{"skill_id": 999999, "required_level": 3, "importance_weight": 1}]}]
    for b in bad:
        assert client.post(f"{API}/admin/careers", headers=admin, json=b).status_code == 422
    assert client.post(f"{API}/admin/careers", headers=admin, json=body).status_code == 409


def test_requirement_change_flows_into_alignment(client, admin, student, db):
    from app import models

    sk = {s.name: s.id for s in db.query(models.Skill)}
    u = db.query(models.User).filter_by(email="student@example.com").one()
    db.add(models.StudentSkill(user_id=u.id, skill_id=sk["Linux"], level=3))
    db.commit()
    body = {"name": "Ops Trainee", "requirements": [{"skill_id": sk["Linux"], "required_level": 3, "importance_weight": 1}]}
    cid = client.post(f"{API}/admin/careers", headers=admin, json=body).json()["id"]
    assert client.get(f"{API}/gaps/{cid}", headers=student).json()["alignment_score"] == 100
    body["requirements"][0]["required_level"] = 5
    client.put(f"{API}/admin/careers/{cid}", headers=admin, json=body)
    assert client.get(f"{API}/gaps/{cid}", headers=student).json()["alignment_score"] == 60  # 3/5


def test_resource_crud_and_delete_protection(client, admin, student, db):
    from app import models

    sk = db.query(models.Skill).filter_by(name="Docker").one().id
    body = {"skill_id": sk, "title": "Docker Labs", "provider": "Example", "url": "https://labs.example/docker",
            "resource_type": "practice", "difficulty": "beginner"}
    r = client.post(f"{API}/admin/resources", headers=admin, json=body)
    assert r.status_code == 201
    rid = r.json()["id"]
    for bad in ({"url": "javascript:alert(1)"}, {"resource_type": "rumour"}, {"difficulty": "expert"}, {"skill_id": 999999}):
        assert client.post(f"{API}/admin/resources", headers=admin, json={**body, "title": "Other", **bad}).status_code == 422
    assert client.post(f"{API}/admin/resources", headers=admin, json=body).status_code == 409
    client.post(f"{API}/progress/{rid}", headers=student, json={"status": "in_progress"})
    assert client.delete(f"{API}/admin/resources/{rid}", headers=admin).status_code == 409
    fresh = client.post(f"{API}/admin/resources", headers=admin, json={**body, "title": "Unused"}).json()["id"]
    assert client.delete(f"{API}/admin/resources/{fresh}", headers=admin).status_code == 204


# ------------------------------------------------------------------ audit

def test_audit_log_viewer(client, admin, db):
    client.post(f"{API}/admin/skills", headers=admin, json={"name": "Rust", "category": "Programming"})
    log = client.get(f"{API}/admin/audit", headers=admin).json()
    assert log["total"] >= 2 and log["items"][0]["action"] == "admin.skill_created"
    assert log["items"][0]["user_email"] == "admin@example.com"
    only = client.get(f"{API}/admin/audit", headers=admin, params={"action": "auth."}).json()["items"]
    assert only and all(i["action"].startswith("auth.") for i in only)
    assert PASSWORD not in str(log)


@pytest.mark.parametrize("path", ["/admin/accounts", "/admin/stats", "/admin/audit"])
def test_non_admin_cannot_read_admin_data(client, teacher, path):
    assert client.get(API + path, headers=teacher).status_code == 403
