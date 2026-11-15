"""Additive schema migration: add any columns the models declare but the DB lacks.

Safe by construction: only ADD COLUMN IF NOT EXISTS. Never drops or alters
existing columns. Run with:
    cd backend
    DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/skill_alignment_db
    python -I ../scripts/migrate.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import inspect, text
from app.db import engine, Base
from app import models  # noqa: F401  ensure mappers are imported

TYPE_MAP = {
    "String": "VARCHAR",
    "Text": "TEXT",
    "Integer": "INTEGER",
    "Float": "DOUBLE PRECISION",
    "Boolean": "BOOLEAN",
    "DateTime": "TIMESTAMPTZ",
}

insp = inspect(engine)
existing = {t.lower() for t in insp.get_table_names()}

# Ensure every table exists first (create_all is additive for missing tables)
Base.metadata.create_all(bind=engine)

insp = inspect(engine)
changed = []
for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
    tname = table.name.lower()
    if tname not in existing:
        continue  # just created above
    db_cols = {c["name"] for c in insp.get_columns(tname)}
    for col in table.columns:
        if col.name in db_cols:
            continue
        coltype = type(col.type).__name__
        sqltype = TYPE_MAP.get(coltype, "TEXT")
        nullable = col.nullable
        # Resolve a server default, if any (e.g. func.now() -> "now()")
        default_sql = None
        if col.server_default is not None:
            try:
                default_sql = col.server_default.arg.text
            except Exception:
                default_sql = None
        with engine.begin() as conn:
            has_rows = bool(conn.execute(text(f'SELECT 1 FROM "{tname}" LIMIT 1')).first())
            if default_sql is not None:
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ADD COLUMN IF NOT EXISTS "{col.name}" '
                    f'{sqltype} NOT NULL DEFAULT {default_sql}'
                ))
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ALTER COLUMN "{col.name}" DROP DEFAULT'
                ))
            elif nullable:
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ADD COLUMN IF NOT EXISTS "{col.name}" {sqltype}'
                ))
            elif not has_rows:
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ADD COLUMN IF NOT EXISTS "{col.name}" {sqltype} NOT NULL'
                ))
            else:
                # Populate existing NULLs with a type-safe sentinel, then enforce NOT NULL.
                if sqltype == "BOOLEAN":
                    sentinel = "false"
                elif sqltype in ("INTEGER", "DOUBLE PRECISION"):
                    sentinel = "0"
                elif sqltype == "TIMESTAMPTZ":
                    sentinel = "now()"
                else:
                    sentinel = "''"
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ADD COLUMN IF NOT EXISTS "{col.name}" {sqltype}'
                ))
                conn.execute(text(
                    f'UPDATE "{tname}" SET "{col.name}" = {sentinel} WHERE "{col.name}" IS NULL'
                ))
                conn.execute(text(
                    f'ALTER TABLE "{tname}" ALTER COLUMN "{col.name}" SET NOT NULL'
                ))
        changed.append(f"{tname}.{col.name} ({sqltype})")

engine.dispose()
print(f"Added {len(changed)} missing column(s):")
for c in changed:
    print("  -", c)