"""Registration, login, sessions, password reset, invitations and role-based access."""

import io
import re
from datetime import timedelta

import pytest

from conftest import PASSWORD, auth_headers, login, make_user, register, take_assessment

API = "/api/v1"
COOKIE = "skillalign_refresh"


def _token(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _mail_token(path: str) -> str:
    from app.services.email import OUTBOX

    body = OUTBOX[-1]["body"]
    return re.search(path + r"\?token=([\w-]+)", body).group(1)


# ------------------------------------------------------------------ registration

def test_register_creates_student_with_profile(client, db):
    from app import models

    r = register(client, email="New.Person@Example.com", phone="+91 98765 43210")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "new.person@example.com" and body["role"] == "student"
    assert "password_hash" not in body
    user = db.query(models.User).filter_by(email="new.person@example.com").one()
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    assert user.student_profile.phone == "+91 98765 43210"


@pytest.mark.parametrize("override,field", [
    ({"password": "short1", "confirm_password": "short1"}, "password"),
    ({"password": "lettersonly", "confirm_password": "lettersonly"}, "password"),
    ({"confirm_password": "Different1"}, "confirm_password"),
    ({"terms_accepted": False}, "terms_accepted"),
    ({"role": "teacher"}, "role"),
    ({"role": "admin"}, "role"),
    ({"email": "not-an-email"}, "email"),
])
def test_register_validation(client, override, field):
    body = {"email": "x@example.com", "full_name": "Some One", "password": PASSWORD,
            "confirm_password": PASSWORD, "terms_accepted": True, **override}
    r = client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 422
    assert field in str(r.json()["detail"])


def test_register_duplicate_email_case_insensitive(client):
    assert register(client, email="dup@example.com").status_code == 201
    assert register(client, email="DUP@example.com").status_code == 409


# ------------------------------------------------------------------ login and sessions

def test_login_sets_httponly_refresh_cookie_and_me_works(client):
    register(client)
    r = login(client, "student@example.com")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"]["role"] == "student"
    assert "refresh_token" not in body
    cookie = r.headers["set-cookie"]
    assert COOKIE in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict")
    assert "Path=/api/v1/auth" in cookie
    me = client.get(f"{API}/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == "student@example.com"
    assert me.json()["last_login_at"] is not None


def test_invalid_credentials_give_identical_errors(client):
    register(client)
    wrong_pw = login(client, "student@example.com", "Wrong-pass1")
    unknown = login(client, "nobody@example.com")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json() == {"detail": "Incorrect email or password"}


def test_inactive_account_cannot_log_in_or_use_tokens(client, db):
    from app import models

    register(client)
    token = _token(login(client, "student@example.com"))
    user = db.query(models.User).filter_by(email="student@example.com").one()
    user.is_active = False
    db.commit()
    assert client.get(f"{API}/auth/me", headers=auth_headers(token)).status_code == 401
    assert login(client, "student@example.com").status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nonsense"}, {"Authorization": "Basic abc"}])
def test_protected_endpoints_require_valid_token(client, headers):
    for path in ["/auth/me", "/careers", "/dashboard", "/resources", "/progress", "/jobs", "/faculty/summary"]:
        assert client.get(API + path, headers=headers).status_code == 401, path


def test_expired_and_tampered_tokens_rejected(client):
    import jwt

    from app.config import settings
    from app.security import utcnow

    register(client)
    good = _token(login(client, "student@example.com"))
    claims = jwt.decode(good, settings.secret_key, algorithms=["HS256"])
    expired = jwt.encode({**claims, "exp": utcnow() - timedelta(seconds=1)}, settings.secret_key, algorithm="HS256")
    forged = jwt.encode({**claims, "role": "admin"}, "some-other-key-that-is-long-enough-123", algorithm="HS256")
    for bad in (expired, forged, good[:-3] + "abc"):
        assert client.get(f"{API}/auth/me", headers=auth_headers(bad)).status_code == 401


def _rotate(client):
    first = client.cookies.get(COOKIE)
    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    second = client.cookies.get(COOKIE)
    assert second and second != first
    return first, second


def _present(client, cookie):
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie, path="/api/v1/auth")
    return client.post(f"{API}/auth/refresh").status_code


def test_refresh_rotates_and_detects_later_reuse(client, db):
    from app import models
    from app.security import utcnow

    register(client)
    login(client, "student@example.com")
    first, second = _rotate(client)
    # Simulate the old token being replayed well after it was rotated out: treated as theft.
    for row in db.query(models.RefreshToken).filter(models.RefreshToken.revoked_at.isnot(None)):
        row.revoked_at = utcnow() - timedelta(minutes=5)
    db.commit()
    assert _present(client, first) == 401
    assert _present(client, second) == 401  # every session of the user was ended


def test_concurrent_refresh_race_does_not_end_sessions(client):
    """Two tabs refreshing at the same moment: the loser gets 401, the new session survives."""
    register(client)
    login(client, "student@example.com")
    first, second = _rotate(client)
    client.cookies.clear()
    client.cookies.set(COOKIE, first, path="/api/v1/auth")
    lost = client.post(f"{API}/auth/refresh")
    assert lost.status_code == 401
    assert COOKIE not in lost.headers.get("set-cookie", "")  # must not wipe the shared cookie
    assert _present(client, second) == 200


def test_refresh_without_cookie_and_logout(client):
    assert client.post(f"{API}/auth/refresh").status_code == 401
    register(client)
    login(client, "student@example.com")
    assert client.post(f"{API}/auth/logout").status_code == 200
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_change_password(client):
    register(client)
    headers = auth_headers(_token(login(client, "student@example.com")))
    bad = client.post(f"{API}/auth/change-password", headers=headers, json={
        "current_password": "Wrong-pass1", "new_password": "N3w-password", "confirm_new_password": "N3w-password"})
    assert bad.status_code == 400
    ok = client.post(f"{API}/auth/change-password", headers=headers, json={
        "current_password": PASSWORD, "new_password": "N3w-password", "confirm_new_password": "N3w-password"})
    assert ok.status_code == 200
    assert login(client, "student@example.com").status_code == 401
    assert login(client, "student@example.com", "N3w-password").status_code == 200


# ------------------------------------------------------------------ password reset

def test_forgot_password_does_not_reveal_accounts(client):
    from app.services.email import OUTBOX

    r = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 202 and len(OUTBOX) == 0
    register(client)
    r2 = client.post(f"{API}/auth/forgot-password", json={"email": "student@example.com"})
    assert r2.status_code == 202 and r2.json() == r.json()
    assert len(OUTBOX) == 1 and OUTBOX[0]["to"] == "student@example.com"


def test_reset_password_is_single_use_and_ends_sessions(client):
    register(client)
    login(client, "student@example.com")
    client.post(f"{API}/auth/forgot-password", json={"email": "student@example.com"})
    token = _mail_token("/reset-password")
    body = {"token": token, "password": "Brand-new1", "confirm_password": "Brand-new1"}
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 200
    assert client.post(f"{API}/auth/reset-password", json=body).status_code == 400  # single use
    assert client.post(f"{API}/auth/refresh").status_code == 401  # old session revoked
    assert login(client, "student@example.com").status_code == 401
    assert login(client, "student@example.com", "Brand-new1").status_code == 200


def test_reset_token_expires(client, db):
    from app import models
    from app.security import utcnow

    register(client)
    client.post(f"{API}/auth/forgot-password", json={"email": "student@example.com"})
    token = _mail_token("/reset-password")
    row = db.query(models.PasswordResetToken).one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    r = client.post(f"{API}/auth/reset-password", json={"token": token, "password": "Brand-new1",
                                                          "confirm_password": "Brand-new1"})
    assert r.status_code == 400


# ------------------------------------------------------------------ rate limiting

def test_login_rate_limit(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_auth", 3)
    codes = [login(client, "nobody@example.com").status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]


# ------------------------------------------------------------------ role-based access

def test_student_cannot_use_staff_or_admin_endpoints(client, student):
    files = {"file": ("j.csv", io.BytesIO(b"title,description\nA,python\n"), "text/csv")}
    assert client.get(f"{API}/faculty/summary", headers=student).status_code == 403
    assert client.post(f"{API}/jobs/import-csv", headers=student, files=files).status_code == 403
    assert client.post(f"{API}/admin/invitations", headers=student,
                       json={"email": "t@example.com", "full_name": "T T"}).status_code == 403
    assert client.get(f"{API}/admin/invitations", headers=student).status_code == 403


def test_teacher_permissions(client, teacher):
    assert client.get(f"{API}/faculty/summary", headers=teacher).status_code == 200
    assert client.get(f"{API}/careers", headers=teacher).status_code == 200
    # Student-only endpoints
    assert client.get(f"{API}/progress", headers=teacher).status_code == 403
    assert client.get(f"{API}/gaps/1", headers=teacher).status_code == 403
    assert client.post(f"{API}/assessments/attempts", headers=teacher, json={"skill_id": 1}).status_code == 403
    # Admin-only endpoints
    assert client.get(f"{API}/admin/invitations", headers=teacher).status_code == 403


def test_role_change_takes_effect_immediately(client, db, student):
    """The role claim inside a token is not trusted; the database is."""
    from app import models
    from app.models import UserRole

    user = db.query(models.User).filter_by(email="student@example.com").one()
    user.role = UserRole.teacher
    db.commit()
    assert client.get(f"{API}/progress", headers=student).status_code == 403
    assert client.get(f"{API}/faculty/summary", headers=student).status_code == 200


def test_students_only_see_their_own_records(client, student, db):
    rid = client.get(f"{API}/resources", headers=student).json()[0]["id"]
    client.post(f"{API}/progress/{rid}", headers=student, json={"status": "completed"})
    take_assessment(client, student, db, "SQL", correct=0)

    register(client, email="other@example.com")
    other = auth_headers(_token(login(client, "other@example.com")))
    assert client.get(f"{API}/assessments/history", headers=other).json() == []
    assert client.get(f"{API}/progress", headers=other).json()["resources"]["total_tracked"] == 0
    assert {r["status"] for r in client.get(f"{API}/resources", headers=other).json()} == {"not_started"}


# ------------------------------------------------------------------ teacher invitations

def test_teacher_invitation_flow(client, admin):
    r = client.post(f"{API}/admin/invitations", headers=admin, json={"email": "Mentor@Example.com", "full_name": "Dr Mentor"})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "pending" and inv["email"] == "mentor@example.com"
    token = _mail_token("/accept-invitation")
    assert inv["invite_url"].endswith(token)

    assert client.get(f"{API}/auth/invitations/{token}").json() == {"email": "mentor@example.com", "full_name": "Dr Mentor"}
    body = {"token": token, "password": "Mentor-pass1", "confirm_password": "Mentor-pass1"}
    created = client.post(f"{API}/auth/accept-invitation", json=body)
    assert created.status_code == 201 and created.json()["role"] == "teacher"
    assert client.post(f"{API}/auth/accept-invitation", json=body).status_code == 400  # single use

    teacher = auth_headers(_token(login(client, "mentor@example.com", "Mentor-pass1")))
    assert client.get(f"{API}/faculty/summary", headers=teacher).status_code == 200
    listed = client.get(f"{API}/admin/invitations", headers=admin).json()
    assert listed[0]["status"] == "accepted"


def test_invitation_revoke_and_duplicates(client, admin):
    register(client, email="taken@example.com")
    assert client.post(f"{API}/admin/invitations", headers=admin,
                       json={"email": "taken@example.com", "full_name": "Taken"}).status_code == 409
    inv = client.post(f"{API}/admin/invitations", headers=admin, json={"email": "t2@example.com", "full_name": "T Two"}).json()
    token = _mail_token("/accept-invitation")
    assert client.post(f"{API}/admin/invitations/{inv['id']}/revoke", headers=admin).json()["status"] == "revoked"
    assert client.get(f"{API}/auth/invitations/{token}").status_code == 400
    assert client.post(f"{API}/admin/invitations/{inv['id']}/revoke", headers=admin).status_code == 400


def test_audit_log_records_auth_events(client, db):
    from app import models

    register(client)
    login(client, "student@example.com")
    login(client, "student@example.com", "Wrong-pass1")
    actions = [a.action for a in db.query(models.AuditLog).order_by(models.AuditLog.id)]
    assert actions == ["auth.register", "auth.login", "auth.login_failed"]
    assert all(PASSWORD not in (a.details or "") for a in db.query(models.AuditLog))


# ------------------------------------------------------------------ CLI

def test_cli_create_admin(client, db, monkeypatch):
    from app import cli

    with pytest.raises(ValueError):
        cli.create_admin(db, "a@example.com", "Admin", "weakpass")
    for bad_email in ("not-an-email", "admin@site.test", "admin@localhost"):
        with pytest.raises(ValueError, match="Invalid email"):
            cli.create_admin(db, bad_email, "Admin", "Adm1n-pass")
    user = cli.create_admin(db, " Root@Example.com ", "Root  Admin", "Adm1n-pass")
    assert user.role.value == "admin" and user.email == "root@example.com" and user.full_name == "Root Admin"
    with pytest.raises(ValueError):
        cli.create_admin(db, "root@example.com", "Again", "Adm1n-pass")
    assert login(client, "root@example.com", "Adm1n-pass").status_code == 200

    monkeypatch.setattr("sys.stdin", io.StringIO("Sec0nd-admin\n"))
    assert cli.main(["create-admin", "--email", "two@example.com", "--name", "Two", "--password-stdin"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("Sec0nd-admin\n"))
    assert cli.main(["create-admin", "--email", "two@example.com", "--name", "Two", "--password-stdin"]) == 1
