"""Phase 6: secure assessment attempts with per-question snapshots; question bank keys.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16

* assessment_questions: bank_key (stable id for bundled questions), index on (skill_id, is_active)
* assessment_attempts: status, difficulty, estimated_level, expires_at, submitted_at.
  Existing (version 1) attempts become status='submitted', submitted_at=created_at.
* assessment_attempt_questions: snapshot columns (text, options, answer key,
  explanation, difficulty, topic, position); answer/is_correct nullable; the link
  to the question becomes ON DELETE SET NULL so history is never cascade-deleted.
* student_skills: last_assessed_at, evidence_attempt_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AQ = "assessment_attempt_questions"


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("assessment_questions") as b:
        b.add_column(sa.Column("bank_key", sa.String(80), nullable=True))
        b.create_unique_constraint("uq_assessment_questions_bank_key", ["bank_key"])
    op.create_index("ix_assessment_questions_skill_active", "assessment_questions", ["skill_id", "is_active"])

    with op.batch_alter_table("assessment_attempts") as b:
        b.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="submitted"))
        b.add_column(sa.Column("difficulty", sa.String(20), nullable=True))
        b.add_column(sa.Column("estimated_level", sa.Integer(), nullable=True))
        b.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE assessment_attempts SET submitted_at = created_at WHERE submitted_at IS NULL")
    op.create_index("ix_attempts_user_status", "assessment_attempts", ["user_id", "status"])

    # Find the existing FK from attempt questions to questions (its name differs between databases).
    fk_name = next(
        (fk["name"] for fk in sa.inspect(bind).get_foreign_keys(AQ)
         if fk["referred_table"] == "assessment_questions"), None
    )
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table(AQ, naming_convention=naming) as b:
        if fk_name:
            b.drop_constraint(fk_name, type_="foreignkey")
        elif bind.dialect.name == "sqlite":
            # Unnamed SQLite FK: name it via the convention so it can be dropped.
            b.drop_constraint("fk_assessment_attempt_questions_question_id_assessment_questions", type_="foreignkey")
        b.alter_column("question_id", existing_type=sa.Integer(), nullable=True)
        b.alter_column("answer", existing_type=sa.String(1), nullable=True)
        b.alter_column("is_correct", existing_type=sa.Boolean(), nullable=True)
        for name, typ in [("question_text", sa.Text()), ("option_a", sa.Text()), ("option_b", sa.Text()),
                          ("option_c", sa.Text()), ("option_d", sa.Text()), ("correct_option", sa.String(1)),
                          ("explanation", sa.Text())]:
            b.add_column(sa.Column(name, typ, nullable=False, server_default=""))
        b.add_column(sa.Column("difficulty", sa.String(20), nullable=False, server_default="beginner"))
        b.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("topic", sa.String(100), nullable=True))
        b.create_foreign_key("fk_attempt_questions_question_id", "assessment_questions",
                             ["question_id"], ["id"], ondelete="SET NULL")

    with op.batch_alter_table("student_skills") as b:
        b.add_column(sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("evidence_attempt_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_student_skills_evidence_attempt", "assessment_attempts",
                             ["evidence_attempt_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    raise NotImplementedError(
        "0005 is not reversible without losing per-question history; restore the pre-upgrade backup instead."
    )
