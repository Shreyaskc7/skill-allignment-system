"""SkillAlign API entry point: app factory, middleware and router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import SessionLocal, engine
from app import models  # noqa: F401  (register mappers)
from app.migrations import ensure_schema_current, upgrade_to_head
from app.routers import admin, assessments, auth, catalog, faculty, gaps, health, jobs, learning
from app.seed import seed

log = logging.getLogger("skillalign")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_tables_on_start:
        log.warning("CREATE_TABLES_ON_START is deprecated and ignored: the schema is managed by Alembic.")
    if settings.auto_migrate:
        upgrade_to_head(settings.database_url)
    ensure_schema_current(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Skill assessment, job-market intelligence, gap analysis and learning recommendations.",
    version="2.0.0-dev",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
for module in (auth, catalog, assessments, gaps, learning, jobs, faculty, admin):
    app.include_router(module.router, prefix=settings.api_v1_prefix)
