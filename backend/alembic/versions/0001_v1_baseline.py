"""v1 baseline: the schema as it existed before version 2.

Revision ID: 0001
Revises:
Create Date: 2026-11-15

ADOPTIVE and ADDITIVE. Version 1 created its tables with
``Base.metadata.create_all`` (plus ``scripts/migrate.py``), so an existing
database may already contain some or all of these tables, possibly from an
older model version with fewer columns. For each table this revision:

* creates it if it does not exist, otherwise
* adds only the columns and indexes that are missing (existing rows are
  back-filled with the model default before NOT NULL is enforced).

It never drops, renames or retypes anything. On PostgreSQL the whole upgrade
runs in one transaction, so any failure leaves the database unchanged.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text("CURRENT_TIMESTAMP")


def _ts(name: str, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=NOW if default else None, nullable=nullable)


def _pk() -> sa.Column:
    return sa.Column("id", sa.Integer(), primary_key=True)


# Back-fill values used when a NOT NULL column without a server default is
# added to an existing table that already has rows (mirrors model defaults).
BACKFILL = {
    ("users", "role"): "student",
    ("users", "password_hash"): "",
    ("users", "is_active"): True,
    ("users", "is_verified"): False,
    ("skills", "category"): "technical",
    ("career_roles", "description"): "",
    ("career_roles", "is_active"): True,
    ("career_role_skills", "required_level"): 3,
    ("career_role_skills", "importance_weight"): 1,
    ("job_postings", "source"): "manual",
    ("assessment_questions", "explanation"): "",
    ("assessment_questions", "difficulty"): "beginner",
    ("assessment_questions", "is_active"): True,
    ("assessment_attempts", "answers_json"): "{}",
    ("student_skills", "level"): 1,
    ("student_skills", "source"): "assessment",
    ("learning_resources", "provider"): "Web",
    ("learning_resources", "resource_type"): "documentation",
    ("learning_resources", "difficulty"): "beginner",
    ("learning_resources", "description"): "",
    ("learning_resources", "is_free"): True,
    ("learning_progress", "status"): "not_started",
    ("learning_progress", "notes"): "",
    ("mentoring_notes", "note_type"): "general",
    ("student_teacher_assignments", "is_active"): True,
}


def tables():
    """(name, columns+constraints, indexes) in foreign-key dependency order."""
    return [
        ("users", [
            _pk(),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(160), nullable=False),
            sa.Column("role", sa.Enum("student", "teacher", "admin", name="userrole"), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("is_verified", sa.Boolean(), nullable=False),
            _ts("created_at"),
            _ts("updated_at"),
        ], [("ix_users_email", ["email"], True)]),
        ("skills", [
            _pk(),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("category", sa.String(60), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("esco_identifier", sa.String(50), nullable=True),
            sa.Column("esco_label", sa.String(200), nullable=True),
            sa.UniqueConstraint("name"),
        ], []),
        ("career_roles", [
            _pk(),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.UniqueConstraint("name"),
        ], []),
        ("job_postings", [
            _pk(),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("company", sa.String(200), nullable=True),
            sa.Column("location", sa.String(160), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("source", sa.String(100), nullable=False),
            sa.Column("posted_date", sa.String(40), nullable=True),
            sa.Column("employment_type", sa.String(60), nullable=True),
            sa.Column("salary_min", sa.Integer(), nullable=True),
            sa.Column("salary_max", sa.Integer(), nullable=True),
            sa.Column("salary_currency", sa.String(10), nullable=True),
            sa.Column("application_url", sa.String(500), nullable=True),
            _ts("created_at"),
        ], []),
        ("student_profiles", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("phone", sa.String(30), nullable=True),
            sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True),
            sa.Column("location", sa.String(160), nullable=True),
            sa.Column("profile_image_url", sa.String(500), nullable=True),
            sa.Column("college", sa.String(200), nullable=True),
            sa.Column("degree", sa.String(120), nullable=True),
            sa.Column("department", sa.String(120), nullable=True),
            sa.Column("specialization", sa.String(120), nullable=True),
            sa.Column("current_semester", sa.Integer(), nullable=True),
            sa.Column("graduation_year", sa.Integer(), nullable=True),
            sa.Column("cgpa", sa.Float(), nullable=True),
            sa.Column("career_interests", sa.Text(), nullable=True),
            sa.Column("target_job_roles", sa.Text(), nullable=True),
            sa.Column("technical_skills", sa.Text(), nullable=True),
            sa.Column("soft_skills", sa.Text(), nullable=True),
            sa.Column("preferred_locations", sa.Text(), nullable=True),
            sa.Column("experience_level", sa.String(60), nullable=True),
            sa.Column("resume_url", sa.String(500), nullable=True),
            _ts("created_at"),
            _ts("updated_at"),
            sa.UniqueConstraint("user_id"),
        ], []),
        ("teacher_profiles", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("phone", sa.String(30), nullable=True),
            sa.Column("profile_image_url", sa.String(500), nullable=True),
            sa.Column("qualification", sa.String(200), nullable=True),
            sa.Column("institution", sa.String(200), nullable=True),
            sa.Column("department", sa.String(120), nullable=True),
            sa.Column("designation", sa.String(120), nullable=True),
            sa.Column("specialization", sa.String(160), nullable=True),
            sa.Column("years_experience", sa.Integer(), nullable=True),
            sa.Column("areas_of_expertise", sa.Text(), nullable=True),
            sa.Column("biography", sa.Text(), nullable=True),
            _ts("created_at"),
            _ts("updated_at"),
            sa.UniqueConstraint("user_id"),
        ], []),
        ("student_teacher_assignments", [
            _pk(),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            _ts("assigned_at"),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removal_reason", sa.Text(), nullable=True),
            sa.UniqueConstraint("student_id", "teacher_id", "is_active", name="uq_active_assignment"),
        ], []),
        ("career_role_skills", [
            _pk(),
            sa.Column("career_role_id", sa.Integer(), sa.ForeignKey("career_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("required_level", sa.Integer(), nullable=False),
            sa.Column("importance_weight", sa.Integer(), nullable=False),
            sa.UniqueConstraint("career_role_id", "skill_id", name="uq_career_role_skill"),
        ], []),
        ("job_skills", [
            _pk(),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
        ], []),
        ("assessment_questions", [
            _pk(),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("option_a", sa.Text(), nullable=False),
            sa.Column("option_b", sa.Text(), nullable=False),
            sa.Column("option_c", sa.Text(), nullable=False),
            sa.Column("option_d", sa.Text(), nullable=False),
            sa.Column("correct_option", sa.String(1), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("difficulty", sa.String(20), nullable=False),
            sa.Column("topic", sa.String(100), nullable=True),
            sa.Column("subtopic", sa.String(100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            _ts("created_at"),
            _ts("updated_at"),
        ], []),
        ("assessment_attempts", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("total_questions", sa.Integer(), nullable=False),
            sa.Column("correct_answers", sa.Integer(), nullable=False),
            sa.Column("score_percent", sa.Float(), nullable=False),
            sa.Column("answers_json", sa.Text(), nullable=False),
            sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
            _ts("created_at"),
        ], []),
        ("assessment_attempt_questions", [
            _pk(),
            sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("answer", sa.String(1), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
        ], []),
        ("student_skills", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            _ts("updated_at"),
            sa.UniqueConstraint("user_id", "skill_id", name="uq_student_skill"),
        ], []),
        ("learning_resources", [
            _pk(),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("provider", sa.String(100), nullable=False),
            sa.Column("url", sa.String(500), nullable=False),
            sa.Column("resource_type", sa.String(40), nullable=False),
            sa.Column("difficulty", sa.String(30), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("is_free", sa.Boolean(), nullable=False),
            sa.Column("estimated_hours", sa.Integer(), nullable=True),
            _ts("created_at"),
        ], []),
        ("learning_progress", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            _ts("updated_at"),
            sa.UniqueConstraint("user_id", "resource_id", name="uq_user_resource"),
        ], []),
        ("mentoring_notes", [
            _pk(),
            sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("note_type", sa.String(30), nullable=False),
            _ts("created_at"),
        ], []),
        ("audit_logs", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(60), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            _ts("created_at"),
        ], [("ix_audit_user_created", ["user_id", "created_at"], False), ("ix_audit_entity", ["entity_type", "entity_id"], False)]),
        ("refresh_tokens", [
            _pk(),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            _ts("created_at"),
        ], [("ix_refresh_tokens_token_hash", ["token_hash"], False), ("ix_refresh_user_expires", ["user_id", "expires_at"], False)]),
    ]


def _add_missing_column(bind, table: str, col: sa.Column) -> None:
    has_rows = bind.execute(sa.text(f'SELECT 1 FROM "{table}" LIMIT 1')).first() is not None
    if bind.dialect.name == "sqlite" and (col.server_default is not None or col.foreign_keys):
        # SQLite cannot ADD COLUMN with a non-constant default or a new foreign key; rebuild the table instead.
        naming = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
        # (SQLite is only used for local tests; the foreign key itself is applied on PostgreSQL.)
        plain = sa.Column(col.name, col.type, nullable=col.nullable, server_default=col.server_default)
        with op.batch_alter_table(table, recreate="always", naming_convention=naming) as batch:
            batch.add_column(plain)
        return
    if col.nullable or col.server_default is not None or not has_rows:
        op.add_column(table, col)
        return
    if (table, col.name) not in BACKFILL:
        raise RuntimeError(f"Cannot add NOT NULL column {table}.{col.name} to a non-empty table without a back-fill value")
    if isinstance(col.type, sa.Enum) and bind.dialect.name == "postgresql":
        col.type.create(bind, checkfirst=True)
    col.nullable = True
    op.add_column(table, col)
    tbl = sa.table(table, sa.column(col.name, col.type))
    op.execute(tbl.update().where(tbl.c[col.name].is_(None)).values({col.name: BACKFILL[(table, col.name)]}))
    with op.batch_alter_table(table) as batch:
        batch.alter_column(col.name, existing_type=col.type, nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, elements, indexes in tables():
        insp = sa.inspect(bind)
        if not insp.has_table(name):
            op.create_table(name, *elements)
        else:
            existing = {c["name"] for c in insp.get_columns(name)}
            for el in elements:
                if isinstance(el, sa.Column) and el.name not in existing:
                    _add_missing_column(bind, name, el)
        present = {i["name"] for i in sa.inspect(bind).get_indexes(name)}
        for ix_name, cols, unique in indexes:
            if ix_name not in present:
                op.create_index(ix_name, name, cols, unique=unique)


def downgrade() -> None:
    raise NotImplementedError("The baseline is not reversible: it may have adopted pre-existing tables and data.")
