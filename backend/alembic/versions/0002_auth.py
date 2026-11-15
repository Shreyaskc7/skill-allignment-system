"""Phase 3: authentication support.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15

* users.last_login_at
* password_reset_tokens, teacher_invitations
* student_teacher_assignments: replace UNIQUE(student_id, teacher_id, is_active),
  which blocked keeping more than one historical (inactive) row per pair,
  with a partial unique index that only covers active rows.
* Deactivate the version 1 shared demo account. Its rows (assessment attempts,
  skill levels, learning progress) are kept, not deleted.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_EMAIL = "student@skillalign.local"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "last_login_at" not in {c["name"] for c in insp.get_columns("users")}:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "teacher_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_teacher_invitations_email", "teacher_invitations", ["email"])

    # Assignment history fix. The old constraint may be absent on very old databases.
    old = {u["name"] for u in insp.get_unique_constraints("student_teacher_assignments")}
    if "uq_active_assignment" in old:
        with op.batch_alter_table("student_teacher_assignments") as batch:
            batch.drop_constraint("uq_active_assignment", type_="unique")
    op.create_index(
        "uq_active_assignment_pair",
        "student_teacher_assignments",
        ["student_id", "teacher_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )

    users = sa.table("users", sa.column("email", sa.String), sa.column("is_active", sa.Boolean))
    op.execute(users.update().where(users.c.email == DEMO_EMAIL).values(is_active=False))


def downgrade() -> None:
    op.drop_index("uq_active_assignment_pair", table_name="student_teacher_assignments")
    with op.batch_alter_table("student_teacher_assignments") as batch:
        batch.create_unique_constraint("uq_active_assignment", ["student_id", "teacher_id", "is_active"])
    op.drop_index("ix_teacher_invitations_email", table_name="teacher_invitations")
    op.drop_table("teacher_invitations")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_login_at")
    # The demo account is intentionally left inactive.
