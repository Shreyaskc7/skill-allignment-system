"""Phase 8: job details, required/optional job skills, skill aliases, parsed posting dates.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16

Existing jobs keep their raw `posted_date` text; `posted_on` is filled where that
text is a recognised date. Existing job-skill links become required + extracted.
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y")


def _parse(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime((text or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def upgrade() -> None:
    with op.batch_alter_table("job_postings") as b:
        b.add_column(sa.Column("posted_on", sa.Date(), nullable=True))
        b.add_column(sa.Column("experience_min_years", sa.Integer(), nullable=True))
        b.add_column(sa.Column("experience_max_years", sa.Integer(), nullable=True))
        b.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        b.add_column(sa.Column("dedupe_hash", sa.String(64), nullable=True))
        b.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_job_postings_created_by_users", "users", ["created_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_job_postings_dedupe_hash", "job_postings", ["dedupe_hash"])

    with op.batch_alter_table("job_skills") as b:
        b.add_column(sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        b.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="extracted"))

    op.create_table(
        "skill_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(100), nullable=False, unique=True),
    )
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"])

    # Back-fill parsed dates for existing postings.
    bind = op.get_bind()
    jobs = sa.table("job_postings", sa.column("id", sa.Integer), sa.column("posted_date", sa.String),
                    sa.column("posted_on", sa.Date))
    for jid, raw in bind.execute(sa.select(jobs.c.id, jobs.c.posted_date).where(jobs.c.posted_date.isnot(None))).all():
        parsed = _parse(raw)
        if parsed:
            bind.execute(jobs.update().where(jobs.c.id == jid).values(posted_on=parsed))


def downgrade() -> None:
    op.drop_index("ix_skill_aliases_skill_id", table_name="skill_aliases")
    op.drop_table("skill_aliases")
    with op.batch_alter_table("job_skills") as b:
        b.drop_column("source")
        b.drop_column("is_required")
    op.drop_index("ix_job_postings_dedupe_hash", table_name="job_postings")
    with op.batch_alter_table("job_postings") as b:
        b.drop_constraint("fk_job_postings_created_by_users", type_="foreignkey")
        for c in ("created_by", "dedupe_hash", "is_active", "experience_max_years", "experience_min_years", "posted_on"):
            b.drop_column(c)
