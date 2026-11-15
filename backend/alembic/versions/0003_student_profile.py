"""Phase 4: student target career and self-reported skills.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("student_profiles") as batch:
        batch.add_column(sa.Column("target_career_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_student_profiles_target_career_id_career_roles", "career_roles",
            ["target_career_id"], ["id"], ondelete="SET NULL",
        )
    op.create_table(
        "student_self_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_student_self_skill"),
    )
    op.create_index("ix_student_self_skills_user_id", "student_self_skills", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_student_self_skills_user_id", table_name="student_self_skills")
    op.drop_table("student_self_skills")
    with op.batch_alter_table("student_profiles") as batch:
        batch.drop_constraint("fk_student_profiles_target_career_id_career_roles", type_="foreignkey")
        batch.drop_column("target_career_id")
