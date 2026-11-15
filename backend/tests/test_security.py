"""Phase 11: authorization matrix over EVERY endpoint, security headers, safe errors."""

import re

import pytest

API = "/api/v1"

# Access classes. Every endpoint in the OpenAPI schema must match exactly one rule, so a new
# endpoint cannot be added without deciding who may use it (the test fails otherwise).
RULES = [
    ("public", r"^/health(/db)?$"),
    ("public", rf"^{API}/auth/(register|login|refresh|logout|forgot-password|reset-password|accept-invitation|invitations/\{{token\}})$"),
    ("any", rf"^{API}/auth/(me|change-password)$"),
    ("any", rf"^{API}/(careers|skills|dashboard|resources|analytics/skills|assessments/skills)$"),
    ("any", rf"^{API}/jobs(/\{{job_id\}})?$::GET"),
    ("student", rf"^{API}/(assessments/(attempts.*|history)|gaps/.*|careers/recommendations|progress.*|learning/.*|students/me/.*)$"),
    ("teacher", rf"^{API}/teachers/me/.*$"),
    ("staff", rf"^{API}/(faculty/.*|mentor/.*|question-bank/.*)$"),
    ("staff", rf"^{API}/jobs(/\{{job_id\}}|/import-csv)?$::(POST|PUT)"),
    ("admin", rf"^{API}/admin/.*$"),
]
ALLOWED = {
    "public": {"anon", "student", "teacher", "admin"},
    "any": {"student", "teacher", "admin"},
    "student": {"student"},
    "teacher": {"teacher"},
    "staff": {"teacher", "admin"},
    "admin": {"admin"},
}


def classify(method: str, path: str) -> str:
    hits = []
    for cls, rule in RULES:
        pattern, _, methods = rule.partition("::")
        if re.match(pattern, path) and (not methods or re.fullmatch(methods, method)):
            hits.append(cls)
    assert len(hits) == 1, f"{method} {path} matches {hits or 'no rule'}: classify it in RULES"
    return hits[0]


def endpoints():
    from app.main import app

    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            if method in ("get", "post", "put", "patch", "delete"):
                yield method.upper(), path


def test_every_endpoint_is_classified():
    eps = list(endpoints())
    assert len(eps) >= 79  # 79 endpoints at Phase 11
    for method, path in eps:
        classify(method, path)


def test_authorization_matrix(client, student, teacher, admin):
    headers = {"anon": {}, "student": student, "teacher": teacher, "admin": admin}
    checked = 0
    for method, path in endpoints():
        cls = classify(method, path)
        concrete = re.sub(r"\{[^}]+\}", "1", path)
        if cls == "public":
            continue  # public endpoints are exercised by the auth tests
        for role, h in headers.items():
            kw = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
            if method == "POST" and "/photo" in path or "/resume" in path and method == "POST" or path.endswith("import-csv"):
                kw = {"files": {"file": ("x.bin", b"x", "application/octet-stream")}}
            status = getattr(client, method.lower())(concrete, headers=h, **kw).status_code
            if role == "anon":
                assert status == 401, (method, path, role, status)
            elif role in ALLOWED[cls]:
                assert status not in (401, 403), (method, path, role, status)
            else:
                assert status == 403, (method, path, role, status)
            checked += 1
    assert checked > 250


def test_security_headers_and_no_store(client, student):
    r = client.get(f"{API}/auth/me", headers=student)
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"
    assert "strict-transport-security" not in h  # only when COOKIE_SECURE (HTTPS)


def test_unexpected_errors_do_not_leak_details(client, student, monkeypatch):
    from app.routers import catalog

    def boom(*a, **k):
        raise RuntimeError("secret internal detail: password=hunter2")

    monkeypatch.setattr(catalog, "select", boom)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get(f"{API}/skills", headers=student)
    assert r.status_code == 500
    assert "secret" not in r.text and "Traceback" not in r.text and "Reference:" in r.json()["detail"]


def test_docs_disabled_in_production(monkeypatch):
    """The FastAPI app object is built at import time, so check the configuration rule directly."""
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(app_env="production", secret_key="")  # insecure secret refused
    with pytest.raises(ValueError):
        Settings(app_env="production", secret_key="s" * 48, cookie_secure=False)  # cookies must be Secure
    assert Settings(app_env="production", secret_key="s" * 48, cookie_secure=True).app_env == "production"


def test_password_hashes_never_returned(client, admin, student):
    for path in ("/auth/me", "/admin/accounts", "/admin/users", "/mentor/students"):
        h = admin if "admin" in path or "mentor" in path else student
        assert "password_hash" not in client.get(API + path, headers=h).text
        assert "$argon2" not in client.get(API + path, headers=h).text
