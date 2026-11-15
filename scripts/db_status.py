"""Report database readiness for the start scripts (run from backend/ with the backend venv).

Output (one line each): CONNECT ok|fail <reason> · REV <current> <head> · ADMINS <n>
Exit codes: 0 ready, 2 cannot connect, 3 migration needed.
Never prints the database password.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.migrations import current_revision, head_revision  # noqa: E402

engine = create_engine(settings.database_url, pool_pre_ping=True)
try:
    with engine.connect():
        pass
except Exception as exc:  # report the cause without echoing the URL
    reason = str(getattr(exc, "orig", exc)).strip().splitlines()[-1] if str(exc).strip() else type(exc).__name__
    print(f"CONNECT fail {reason}")
    sys.exit(2)
print("CONNECT ok")

current, head = current_revision(engine), head_revision()
print(f"REV {current or 'none'} {head}")
if current != head:
    sys.exit(3)

from app import models  # noqa: E402

with engine.connect() as conn:
    n = conn.execute(select(func.count(models.User.id)).where(
        models.User.role == models.UserRole.admin, models.User.is_active.is_(True))).scalar()
print(f"ADMINS {n}")
