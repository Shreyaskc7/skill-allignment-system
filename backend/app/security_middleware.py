"""HTTP hardening: security headers and safe error responses."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

log = logging.getLogger("skillalign.errors")

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # JSON/API responses never need to load anything; the interactive docs (dev only) do.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            h.setdefault("Content-Security-Policy", API_CSP)
        if request.url.path.startswith(f"{settings.api_v1_prefix}/"):
            h.setdefault("Cache-Control", "no-store")
        if settings.cookie_secure:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def install(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # Never return stack traces or internal messages to clients; log them with a reference id.
        ref = uuid.uuid4().hex[:12]
        log.exception("Unhandled error %s on %s %s", ref, request.method, request.url.path)
        return JSONResponse({"detail": f"An unexpected error occurred. Reference: {ref}"}, status_code=500)
