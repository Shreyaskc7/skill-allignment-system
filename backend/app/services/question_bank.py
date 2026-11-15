"""Load the bundled question bank (app/question_bank/*.json) into the database.

* Each question gets a stable ``bank_key`` = "<file slug>:<sha1(question text)[:12]>".
* Loading is idempotent: a key already in the database is never overwritten, so
  edits and deactivations made by staff in the Question Bank screen are kept.
* Version 1 questions with identical text are adopted (their key is set) instead
  of being duplicated, so their attempt history stays linked.
"""

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

BANK_DIR = Path(__file__).resolve().parents[1] / "question_bank"
DIFFICULTIES = ("beginner", "intermediate", "advanced")


class QuestionBankError(ValueError):
    pass


def bank_key(slug: str, text: str) -> str:
    return f"{slug}:{hashlib.sha1(text.strip().encode('utf-8')).hexdigest()[:12]}"


def validate_question(q: dict, where: str) -> None:
    def fail(msg):
        raise QuestionBankError(f"{where}: {msg}")

    text = q.get("question")
    if not isinstance(text, str) or not text.strip():
        fail("missing question text")
    opts = q.get("options")
    if not isinstance(opts, list) or len(opts) != 4 or not all(isinstance(o, str) and o.strip() for o in opts):
        fail("needs exactly four non-empty options")
    # Case-sensitive on purpose: e.g. React's `onClick` vs `onclick` is a meaningful distinction.
    if len({o.strip() for o in opts}) != 4:
        fail("options must be distinct")
    if q.get("correct") not in ("A", "B", "C", "D"):
        fail("correct must be A, B, C or D")
    if q.get("difficulty") not in DIFFICULTIES:
        fail(f"difficulty must be one of {DIFFICULTIES}")
    if not isinstance(q.get("explanation"), str) or not q["explanation"].strip():
        fail("missing explanation")


def read_bank(directory: Path = BANK_DIR) -> list[tuple[str, str, list[dict]]]:
    """Return [(slug, skill name, questions)] after validating every file."""
    files = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        skill, questions = data.get("skill"), data.get("questions")
        if not isinstance(skill, str) or not isinstance(questions, list):
            raise QuestionBankError(f"{path.name}: expected {{'skill': str, 'questions': list}}")
        seen = set()
        for i, q in enumerate(questions, 1):
            validate_question(q, f"{path.name} question {i}")
            norm = " ".join(q["question"].lower().split())
            if norm in seen:
                raise QuestionBankError(f"{path.name} question {i}: duplicate question text")
            seen.add(norm)
        files.append((path.stem, skill, questions))
    return files


def load_question_bank(db: Session, directory: Path = BANK_DIR) -> int:
    """Insert missing bank questions. Returns the number of questions added."""
    bank = read_bank(directory)
    if not bank:
        return 0
    skills = {s.name: s.id for s in db.scalars(select(models.Skill))}
    keyed = set(db.scalars(select(models.AssessmentQuestion.bank_key).where(models.AssessmentQuestion.bank_key.isnot(None))))
    unkeyed = {
        (q.skill_id, " ".join(q.question.split())): q
        for q in db.scalars(select(models.AssessmentQuestion).where(models.AssessmentQuestion.bank_key.is_(None)))
    }
    added = 0
    for slug, skill_name, questions in bank:
        skill_id = skills.get(skill_name)
        if skill_id is None:
            raise QuestionBankError(f"{slug}.json: unknown skill '{skill_name}'")
        for q in questions:
            key = bank_key(slug, q["question"])
            if key in keyed:
                continue
            existing = unkeyed.pop((skill_id, " ".join(q["question"].split())), None)
            if existing is not None:  # adopt the version 1 row
                existing.bank_key = key
                existing.topic = existing.topic or q.get("topic")
                existing.subtopic = existing.subtopic or q.get("subtopic")
            else:
                a, b, c, d = q["options"]
                db.add(models.AssessmentQuestion(
                    skill_id=skill_id, question=q["question"].strip(), option_a=a, option_b=b, option_c=c, option_d=d,
                    correct_option=q["correct"], explanation=q["explanation"].strip(), difficulty=q["difficulty"],
                    topic=(q.get("topic") or None), subtopic=(q.get("subtopic") or None), is_active=True,
                    bank_key=key,
                ))
                added += 1
            keyed.add(key)
    db.flush()
    return added
