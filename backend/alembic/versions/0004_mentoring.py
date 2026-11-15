"""Phase 5: mentoring notes can recommend a resource and be private to staff.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("mentoring_notes") as batch:
        batch.add_column(sa.Column("resource_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("visible_to_student", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        batch.create_foreign_key(
            "fk_mentoring_notes_resource_id_learning_resources", "learning_resources",
            ["resource_id"], ["id"], ondelete="SET NULL",
        )
    op.create_index("ix_mentoring_notes_student_created", "mentoring_notes", ["student_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_mentoring_notes_student_created", table_name="mentoring_notes")
    with op.batch_alter_table("mentoring_notes") as batch:
        batch.drop_constraint("fk_mentoring_notes_resource_id_learning_resources", type_="foreignkey")
        batch.drop_column("visible_to_student")
        batch.drop_column("resource_id")
