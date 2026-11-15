from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "skill-alignment-api", "environment": settings.app_env}


@router.get("/health/db")
def db_health():
    try:
        check_database_connection()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(503, "Database connection unavailable") from e
