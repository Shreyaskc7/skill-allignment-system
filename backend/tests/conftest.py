"""Test configuration.

Tests run ONLY against the database in TEST_DATABASE_URL and never against the
developer's real DATABASE_URL. Every table in that database is dropped and
recreated, so point it at a throwaway database (CI uses a disposable
PostgreSQL service container).
"""

import os

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    # Must be set before any `app` module is imported, because the engine is
    # created from settings at import time.
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["CREATE_TABLES_ON_START"] = "true"


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set; refusing to touch a real database")
    for item in items:
        if "client" in item.fixturenames:
            item.add_marker(skip)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.db import Base, engine
    from app import models  # noqa: F401  (register mappers)
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # runs startup: create_all + seed
        yield c
    Base.metadata.drop_all(bind=engine)
