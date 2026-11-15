"""Audit log helper. Records are added to the caller's session and committed with it."""

import json

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


def client_ip(request: Request | None) -> str | None:
    return request.client.host if request is not None and request.client else None


def audit(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        models.AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details else None,
            ip_address=client_ip(request),
        )
    )
