"""Phase 11: indexes for frequently filtered foreign keys and the audit log.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16

PostgreSQL does not index foreign keys automatically; these cover the filters used
by job skill search, mentor scoping, learning paths and the audit log viewer.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_job_skills_skill_id", "job_skills", ["skill_id"]),
    ("ix_assignments_teacher_active", "student_teacher_assignments", ["teacher_id", "is_active"]),
    ("ix_learning_resources_skill_id", "learning_resources", ["skill_id"]),
    ("ix_audit_created_at", "audit_logs", ["created_at"]),
]


def upgrade() -> None:
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
