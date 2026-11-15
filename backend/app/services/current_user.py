"""Who the request is acting for.

TEMPORARY (Phase 2): every request acts as the seeded demo student.
Phase 3 replaces this with JWT authentication (`get_current_user`), and the
demo account is kept, inactive, so its existing records are preserved.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

DEMO_STUDENT_EMAIL = "student@skillalign.local"


def get_demo_student(db: Session) -> models.User:
    return db.scalar(select(models.User).where(models.User.email == DEMO_STUDENT_EMAIL))
