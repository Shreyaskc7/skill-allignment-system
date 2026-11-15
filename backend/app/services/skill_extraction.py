"""Dictionary/regex baseline for extracting catalogue skills from job text.

This is a transparent rule-based extractor, not a machine-learning model.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.seed_data import CATALOG

ALIASES = {
    "js": "JavaScript",
    "postgres": "PostgreSQL",
    "powerbi": "Power BI",
    "problem-solving": "Problem Solving",
    "data analytics": "Data Analysis",
}


def _mentions(term: str, text_lower: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text_lower) is not None


def extract_skills(text: str) -> list[str]:
    """Return sorted, de-duplicated canonical skill names found in ``text``."""
    low = text.lower()
    found = [canonical for term, canonical in ALIASES.items() if _mentions(term, low)]
    found += [name for name in CATALOG if _mentions(name.lower(), low)]
    return sorted(set(found))


def get_or_create_skill(db: Session, name: str) -> models.Skill | None:
    name = name.strip()
    if not name:
        return None
    obj = db.scalar(select(models.Skill).where(func.lower(models.Skill.name) == name.lower()))
    if not obj:
        cat, desc = CATALOG.get(name, ("Other", "Extracted from job description"))
        obj = models.Skill(name=name[:100], category=cat, description=desc)
        db.add(obj)
        db.flush()
    return obj
