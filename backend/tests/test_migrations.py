"""Alembic migrations: fresh databases and adoption of existing version 1 databases."""

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

from conftest import TEST_DATABASE_URL


def _upgrade(rev="head"):
    from app.migrations import alembic_config

    command.upgrade(alembic_config(TEST_DATABASE_URL), rev)


def _diff(engine):
    from app.db import Base

    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)


def test_fresh_database_matches_models(engine_clean):
    from app.migrations import current_revision, head_revision

    _upgrade()
    assert current_revision(engine_clean) == head_revision()
    assert _diff(engine_clean) == []


def test_startup_refuses_unmigrated_database(engine_clean):
    from app.migrations import SchemaOutOfDate, ensure_schema_current

    with pytest.raises(SchemaOutOfDate, match="alembic upgrade head"):
        ensure_schema_current(engine_clean)


def test_adopts_full_v1_database_created_by_create_all(engine_clean):
    """v1 used create_all (no alembic_version). Simulate it, add v1-style data, then upgrade."""
    _upgrade("0001")
    with engine_clean.begin() as conn:
        conn.execute(sa.text("DROP TABLE alembic_version"))
        conn.execute(sa.text(
            "INSERT INTO users (id, email, full_name, role, password_hash, is_active, is_verified) "
            "VALUES (1, 'student@skillalign.local', 'Student Demo', 'student', '', true, false)"))
        conn.execute(sa.text("INSERT INTO skills (id, name, category) VALUES (1, 'Python', 'Programming')"))
        conn.execute(sa.text(
            "INSERT INTO assessment_attempts (user_id, skill_id, total_questions, correct_answers, score_percent, answers_json) "
            "VALUES (1, 1, 5, 4, 80, '{}')"))
        conn.execute(sa.text(
            "INSERT INTO student_teacher_assignments (student_id, teacher_id, is_active) VALUES (1, 1, false)"))

    _upgrade()

    with engine_clean.connect() as conn:
        assert conn.execute(sa.text("SELECT is_active FROM users WHERE id = 1")).scalar() in (False, 0)
        assert conn.execute(sa.text("SELECT count(*) FROM assessment_attempts")).scalar() == 1  # data kept
        # Assignment history now allows several inactive rows for the same pair...
        conn.execute(sa.text("INSERT INTO student_teacher_assignments (student_id, teacher_id, is_active) VALUES (1, 1, false)"))
        conn.execute(sa.text("INSERT INTO student_teacher_assignments (student_id, teacher_id, is_active) VALUES (1, 1, true)"))
        # ...but only one active one.
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text("INSERT INTO student_teacher_assignments (student_id, teacher_id, is_active) VALUES (1, 1, true)"))
        conn.rollback()
    assert _diff(engine_clean) == []


def test_adopts_older_partial_v1_schema(engine_clean):
    """An early v1 database: fewer tables and columns, existing rows. Upgrade adds what is missing."""
    md = sa.MetaData()
    sa.Table("users", md,
             sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("email", sa.String(255), nullable=False, unique=True),
             sa.Column("full_name", sa.String(160), nullable=False),
             sa.Column("role", sa.String(20), nullable=False))
    sa.Table("skills", md,
             sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("name", sa.String(100), nullable=False, unique=True))
    sa.Table("assessment_questions", md,
             sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("skill_id", sa.Integer, sa.ForeignKey("skills.id"), nullable=False),
             sa.Column("question", sa.Text, nullable=False),
             sa.Column("option_a", sa.Text, nullable=False), sa.Column("option_b", sa.Text, nullable=False),
             sa.Column("option_c", sa.Text, nullable=False), sa.Column("option_d", sa.Text, nullable=False),
             sa.Column("correct_option", sa.String(1), nullable=False))
    md.create_all(engine_clean)
    with engine_clean.begin() as conn:
        conn.execute(sa.text("INSERT INTO users (email, full_name, role) VALUES ('student@skillalign.local', 'Demo', 'student')"))
        conn.execute(sa.text("INSERT INTO skills (name) VALUES ('SQL')"))
        conn.execute(sa.text("INSERT INTO assessment_questions (skill_id, question, option_a, option_b, option_c, option_d, correct_option) "
                             "VALUES (1, 'Q?', 'a', 'b', 'c', 'd', 'B')"))

    _upgrade()

    with engine_clean.connect() as conn:
        user = conn.execute(sa.text("SELECT password_hash, is_active, is_verified FROM users")).one()
        assert user.password_hash == "" and not user.is_active and not user.is_verified  # back-filled, demo disabled
        skill = conn.execute(sa.text("SELECT name, category FROM skills")).one()
        assert tuple(skill) == ("SQL", "technical")
        q = conn.execute(sa.text("SELECT question, difficulty, explanation, is_active FROM assessment_questions")).one()
        assert q.question == "Q?" and q.difficulty == "beginner" and q.explanation == "" and q.is_active
        tables = set(sa.inspect(conn).get_table_names())
    assert {"career_roles", "learning_progress", "refresh_tokens", "teacher_invitations"} <= tables


def test_empty_password_hash_never_authenticates():
    from app.security import verify_password

    assert verify_password("", "") is False
