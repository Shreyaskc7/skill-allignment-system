"""Assessment attempts: delivery, validation, scoring and results.

Rules (Phase 6):
* Questions are chosen on the server (cryptographically random) and stored with the
  attempt; the browser never receives answer keys before submission.
* Only the delivered questions are scored. Unknown or duplicate question ids and
  options other than A-D are rejected. An attempt can be submitted once, only by
  its owner, and (if timed) within the time limit plus a short grace period.
* Each delivered question is snapshotted, so later question-bank edits never change
  a past result. The skill level is updated only after a successful submission.
"""

import json
import secrets
from collections import defaultdict
from datetime import timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.security import utcnow
from app.services.alignment import LEVEL_BANDS, estimate_level

MIN_QUESTIONS = 5
MAX_QUESTIONS = 30
SECONDS_PER_QUESTION = 90
GRACE_SECONDS = 30
_rng = secrets.SystemRandom()


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def submitted_only():
    return models.AssessmentAttempt.status == "submitted"


def available_skills(db: Session) -> list[dict]:
    rows = db.execute(
        select(models.Skill.id, models.Skill.name, models.Skill.category, models.AssessmentQuestion.difficulty,
               func.count(models.AssessmentQuestion.id))
        .join(models.AssessmentQuestion, models.AssessmentQuestion.skill_id == models.Skill.id)
        .where(models.AssessmentQuestion.is_active.is_(True))
        .group_by(models.Skill.id, models.Skill.name, models.Skill.category, models.AssessmentQuestion.difficulty)
    ).all()
    skills: dict[int, dict] = {}
    for sid, name, cat, diff, n in rows:
        s = skills.setdefault(sid, {"id": sid, "name": name, "category": cat, "question_count": 0,
                                    "by_difficulty": {"beginner": 0, "intermediate": 0, "advanced": 0}})
        s["question_count"] += n
        s["by_difficulty"][diff] = s["by_difficulty"].get(diff, 0) + n
    return sorted((s for s in skills.values() if s["question_count"] >= MIN_QUESTIONS), key=lambda s: s["name"])


def _pick(pool: list[models.AssessmentQuestion], n: int, difficulty: str) -> list[models.AssessmentQuestion]:
    if difficulty != "mixed":
        return _rng.sample(pool, n)
    # Mixed: interleave shuffled difficulty groups so every level is represented.
    groups = defaultdict(list)
    for q in pool:
        groups[q.difficulty].append(q)
    for g in groups.values():
        _rng.shuffle(g)
    order = [g for d in ("beginner", "intermediate", "advanced") if (g := groups.get(d))]
    picked = []
    while len(picked) < n:
        for g in order:
            if g and len(picked) < n:
                picked.append(g.pop())
    _rng.shuffle(picked)
    return picked


def expire_if_needed(db: Session, attempt: models.AssessmentAttempt) -> bool:
    if attempt.status == "in_progress" and attempt.expires_at is not None:
        if utcnow() > _aware(attempt.expires_at) + timedelta(seconds=GRACE_SECONDS):
            attempt.status = "expired"
            db.flush()
            return True
    return False


def start_attempt(db: Session, user: models.User, skill_id: int, count: int, difficulty: str, timed: bool,
                  restart: bool) -> tuple[models.AssessmentAttempt, bool]:
    """Return (attempt, resumed). An unfinished attempt for the same skill is resumed unless restart=True."""
    skill = db.get(models.Skill, skill_id)
    if skill is None:
        raise HTTPException(404, "Skill not found")
    current = db.scalar(
        select(models.AssessmentAttempt)
        .where(models.AssessmentAttempt.user_id == user.id, models.AssessmentAttempt.skill_id == skill_id,
               models.AssessmentAttempt.status == "in_progress")
        .order_by(models.AssessmentAttempt.id.desc())
    )
    if current is not None and not expire_if_needed(db, current):
        if not restart:
            return current, True
        current.status = "abandoned"

    stmt = select(models.AssessmentQuestion).where(
        models.AssessmentQuestion.skill_id == skill_id, models.AssessmentQuestion.is_active.is_(True))
    if difficulty != "mixed":
        stmt = stmt.where(models.AssessmentQuestion.difficulty == difficulty)
    pool = list(db.scalars(stmt))
    if len(pool) < MIN_QUESTIONS:
        raise HTTPException(422, f"Not enough {'' if difficulty == 'mixed' else difficulty + ' '}questions for "
                                 f"{skill.name} yet (need at least {MIN_QUESTIONS}, found {len(pool)}).")
    n = min(count, len(pool))
    chosen = _pick(pool, n, difficulty)
    now = utcnow()
    attempt = models.AssessmentAttempt(
        user_id=user.id, skill_id=skill_id, status="in_progress", difficulty=difficulty, total_questions=n,
        correct_answers=0, score_percent=0.0,
        expires_at=now + timedelta(seconds=SECONDS_PER_QUESTION * n) if timed else None,
    )
    attempt.questions = [
        models.AssessmentAttemptQuestion(
            question_id=q.id, position=i, question_text=q.question, option_a=q.option_a, option_b=q.option_b,
            option_c=q.option_c, option_d=q.option_d, correct_option=q.correct_option, explanation=q.explanation,
            difficulty=q.difficulty, topic=q.topic,
        )
        for i, q in enumerate(chosen, 1)
    ]
    db.add(attempt)
    db.flush()
    return attempt, False


def delivery(attempt: models.AssessmentAttempt, resumed: bool = False) -> dict:
    """In-progress view: questions WITHOUT answer keys or explanations."""
    return {
        "attempt_id": attempt.id,
        "skill_id": attempt.skill_id,
        "skill": attempt.skill.name,
        "status": attempt.status,
        "difficulty": attempt.difficulty,
        "resumed": resumed,
        "started_at": attempt.created_at,
        "expires_at": attempt.expires_at,
        "server_time": utcnow(),
        "questions": [
            {"id": q.question_id, "position": q.position, "question": q.question_text, "difficulty": q.difficulty,
             "options": {"A": q.option_a, "B": q.option_b, "C": q.option_c, "D": q.option_d}}
            for q in attempt.questions
        ],
    }


def submit_attempt(db: Session, user: models.User, attempt_id: int, answers: list[tuple[int, str]]) -> models.AssessmentAttempt:
    attempt = owned_attempt(db, user, attempt_id)
    if expire_if_needed(db, attempt):
        db.commit()
        raise HTTPException(409, "The time limit for this attempt has passed; it was not scored.")
    if attempt.status != "in_progress":
        raise HTTPException(409, f"This attempt is already {attempt.status}.")
    ids = [qid for qid, _ in answers]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Each question can be answered only once.")
    delivered = {q.question_id: q for q in attempt.questions}
    if unknown := sorted(set(ids) - set(delivered)):
        raise HTTPException(422, f"Answers include questions that were not part of this attempt: {unknown}")

    given = dict(answers)
    correct = 0
    for qid, q in delivered.items():
        q.answer = given.get(qid)
        q.is_correct = q.answer is not None and q.answer == q.correct_option
        correct += q.is_correct
    now = utcnow()
    total = attempt.total_questions
    attempt.correct_answers = correct
    attempt.score_percent = round(correct / total * 100, 2) if total else 0.0
    attempt.estimated_level = estimate_level(attempt.score_percent)
    attempt.answers_json = json.dumps({str(k): v for k, v in given.items()})
    attempt.time_spent_seconds = int((now - _aware(attempt.created_at)).total_seconds()) if attempt.created_at else None
    attempt.status, attempt.submitted_at = "submitted", now

    skill = db.scalar(select(models.StudentSkill).where(
        models.StudentSkill.user_id == user.id, models.StudentSkill.skill_id == attempt.skill_id))
    if skill is None:
        skill = models.StudentSkill(user_id=user.id, skill_id=attempt.skill_id)
        db.add(skill)
    skill.level, skill.source = attempt.estimated_level, "assessment"
    skill.last_assessed_at, skill.evidence_attempt_id = now, attempt.id
    db.flush()
    return attempt


def owned_attempt(db: Session, user: models.User, attempt_id: int) -> models.AssessmentAttempt:
    attempt = db.scalar(
        select(models.AssessmentAttempt)
        .options(selectinload(models.AssessmentAttempt.questions), selectinload(models.AssessmentAttempt.skill))
        .where(models.AssessmentAttempt.id == attempt_id)
    )
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    return attempt


def _breakdown(items, key):
    out = defaultdict(lambda: {"correct": 0, "total": 0})
    for q in items:
        k = key(q) or "General"
        out[k]["total"] += 1
        out[k]["correct"] += bool(q.is_correct)
    return [{"name": k, **v, "percent": round(v["correct"] / v["total"] * 100)} for k, v in sorted(out.items())]


def result(attempt: models.AssessmentAttempt) -> dict:
    qs = attempt.questions
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    return {
        "attempt_id": attempt.id,
        "skill_id": attempt.skill_id,
        "skill": attempt.skill.name,
        "status": attempt.status,
        "difficulty": attempt.difficulty,
        "total": attempt.total_questions,
        "correct": attempt.correct_answers,
        "unanswered": sum(1 for q in qs if q.answer is None),
        "score_percent": attempt.score_percent,
        "estimated_level": attempt.estimated_level,
        "level_bands": LEVEL_BANDS,
        "time_spent_seconds": attempt.time_spent_seconds,
        "submitted_at": attempt.submitted_at or attempt.created_at,
        "by_difficulty": sorted(_breakdown(qs, lambda q: q.difficulty), key=lambda x: order.get(x["name"], 9)),
        "by_topic": _breakdown(qs, lambda q: q.topic),
        "review": [
            {"question_id": q.question_id, "position": q.position, "question": q.question_text,
             "options": {"A": q.option_a, "B": q.option_b, "C": q.option_c, "D": q.option_d},
             "your_answer": q.answer, "correct_option": q.correct_option, "is_correct": bool(q.is_correct),
             "explanation": q.explanation, "difficulty": q.difficulty, "topic": q.topic}
            for q in qs
        ],
        # Version 1 attempts were not stored per question.
        "detail_available": bool(qs),
    }
