"""Skill extraction from job text: a transparent, rule-based dictionary extractor.

This is NOT a machine-learning model. It is designed so a trained model (e.g. a
SkillSpan-style token classifier) can replace it later: anything implementing
`SkillExtractor.extract(text) -> list[Extraction]` can be plugged into the job services.

Rules (Phase 8):
* catalogue skill names plus aliases (table `skill_aliases`), case-insensitive, whole-word;
* multi-word phrases; longest match wins, overlapping shorter matches are ignored;
* negation: a term preceded within the same clause by "no", "not", "without" or "never" is skipped;
* context: "excel" followed by "in"/"at" is the verb, not Microsoft Excel;
* optional vs required: a skill only mentioned in clauses with cues such as "nice to have",
  "preferred", "a plus", "bonus" or "good to have" is optional; otherwise it is required.

`v1_extract_skills` keeps the version 1 baseline for evaluation (scripts/evaluate_extractor.py).
"""

import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.seed_data import CATALOG

# alias (lower case) -> catalogue skill name. Seeded into `skill_aliases`; staff can add more there.
DEFAULT_ALIASES = {
    "js": "JavaScript", "ecmascript": "JavaScript", "es6": "JavaScript",
    "postgres": "PostgreSQL", "postgre sql": "PostgreSQL", "psql": "PostgreSQL",
    "powerbi": "Power BI", "power-bi": "Power BI", "microsoft power bi": "Power BI",
    "problem-solving": "Problem Solving", "problem solver": "Problem Solving", "analytical thinking": "Problem Solving",
    "data analytics": "Data Analysis", "data analyst skills": "Data Analysis", "analysing data": "Data Analysis",
    "analyzing data": "Data Analysis",
    "ms excel": "Excel", "microsoft excel": "Excel", "advanced excel": "Excel", "spreadsheets": "Excel",
    "reactjs": "React", "react.js": "React", "react js": "React",
    "ml": "Machine Learning", "machine-learning": "Machine Learning",
    "statistical analysis": "Statistics", "statistical methods": "Statistics",
    "github": "Git", "gitlab": "Git", "version control": "Git",
    "unix": "Linux", "shell scripting": "Linux",
    "containers": "Docker", "containerization": "Docker", "dockerfile": "Docker",
    "rest api with fastapi": "FastAPI", "fast api": "FastAPI",
    "html5": "HTML", "css3": "CSS",
    "communication skills": "Communication", "verbal communication": "Communication",
    "written communication": "Communication", "stakeholder communication": "Communication",
    "team player": "Teamwork", "collaboration": "Teamwork", "team work": "Teamwork",
    "data structure": "Data Structures", "dsa": "Data Structures",
    "algorithm": "Algorithms", "algorithmic": "Algorithms",
    "numpy arrays": "NumPy", "pandas dataframes": "Pandas",
    "core java": "Java", "java 17": "Java", "j2ee": "Java",
    "python3": "Python", "python 3": "Python",
}

OPTIONAL_CUES = re.compile(
    r"nice[- ]to[- ]have|good[- ]to[- ]have|preferred|preferable|is a plus|are a plus|a plus\b|bonus|"
    r"desirable|advantageous|an advantage|optional|not mandatory|familiarity is welcome"
)
NEGATION = re.compile(r"\b(?:no|not|without|never)\b(?![^,;:]*\b(?:but|however)\b)[^,;:]{0,40}$")
CLAUSE_SPLIT = re.compile(r"[.;\n•●▪]+|\s-\s|(?<=[a-z]):\s")


@dataclass(frozen=True)
class Extraction:
    skill: str
    required: bool
    evidence: str


class SkillExtractor(Protocol):
    def extract(self, text: str) -> list[Extraction]: ...


def _pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9+#])" + re.escape(term) + r"(?![a-z0-9+#])")


class DictionaryExtractor:
    """Rule-based extractor over catalogue names and aliases."""

    def __init__(self, terms: dict[str, str]):
        # longest terms first so "data analysis" wins over shorter overlapping terms
        self.terms = sorted(((t.lower(), s) for t, s in terms.items()), key=lambda x: -len(x[0]))
        self.patterns = [(_pattern(t), t, s) for t, s in self.terms]

    def extract(self, text: str) -> list[Extraction]:
        found: dict[str, Extraction] = {}
        for clause in CLAUSE_SPLIT.split(" ".join((text or "").lower().split())):
            optional = bool(OPTIONAL_CUES.search(clause))
            taken: list[tuple[int, int]] = []
            for pattern, term, skill in self.patterns:
                for m in pattern.finditer(clause):
                    start, end = m.span()
                    if any(start < e and end > s for s, e in taken):
                        continue  # overlaps a longer match already taken
                    if NEGATION.search(clause[:start]):
                        continue
                    if term == "excel" and re.match(r"\s+(?:in|at)\b", clause[end:]):
                        continue  # "excel in/at ..." is the verb
                    taken.append((start, end))
                    prev = found.get(skill)
                    required = not optional or (prev is not None and prev.required)
                    if prev is None or (required and not prev.required):
                        found[skill] = Extraction(skill, required, clause[max(0, start - 30): end + 30].strip())
        return sorted(found.values(), key=lambda e: e.skill)


def default_terms() -> dict[str, str]:
    terms = {name.lower(): name for name in CATALOG}
    terms.update({a: s for a, s in DEFAULT_ALIASES.items() if s in CATALOG})
    return terms


def extractor_from_db(db: Session) -> DictionaryExtractor:
    terms = {name.lower(): name for name in db.scalars(select(models.Skill.name))}
    for alias, name in db.execute(
        select(models.SkillAlias.alias, models.Skill.name).join(models.Skill, models.Skill.id == models.SkillAlias.skill_id)
    ).all():
        terms[alias.lower()] = name
    return DictionaryExtractor(terms)


def seed_aliases(db: Session) -> None:
    """Insert default aliases that are missing (idempotent; never removes staff-added ones)."""
    skills = {s.name: s.id for s in db.scalars(select(models.Skill))}
    existing = set(db.scalars(select(models.SkillAlias.alias)))
    for alias, name in DEFAULT_ALIASES.items():
        if alias not in existing and name in skills:
            db.add(models.SkillAlias(alias=alias, skill_id=skills[name]))
    db.flush()


def extract_skills(text: str) -> list[str]:
    """Skill names found in ``text`` (required or optional) using the default dictionary."""
    return [e.skill for e in DictionaryExtractor(default_terms()).extract(text)]


# ------------------------------------------------------------------ version 1 baseline (for evaluation only)

V1_ALIASES = {"js": "JavaScript", "postgres": "PostgreSQL", "powerbi": "Power BI",
              "problem-solving": "Problem Solving", "data analytics": "Data Analysis"}


def v1_extract_skills(text: str) -> list[str]:
    low = text.lower()
    found = [c for t, c in V1_ALIASES.items() if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)]
    found += [n for n in CATALOG if re.search(r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])", low)]
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
