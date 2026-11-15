"""SkillAlign API entry point: app factory, middleware and router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app import models  # noqa: F401  (register mappers before create_all)
from app.routers import assessments, catalog, faculty, gaps, health, jobs, learning
from app.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_tables_on_start:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Skill assessment, job-market intelligence, gap analysis and learning recommendations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
for module in (catalog, assessments, gaps, learning, jobs, faculty):
    app.include_router(module.router, prefix=settings.api_v1_prefix)
