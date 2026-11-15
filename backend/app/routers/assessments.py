"""Skill assessments: question delivery, submission and history.

Known limitation (fixed in Phase 6): submission is scored against every
question of the skill, not only the questions that were delivered.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.services.alignment import estimate_level
from app.deps import get_current_user, require_student

router = APIRouter(prefix="/assessments", tags=["assessments"], dependencies=[Depends(get_current_user)])


@router.get("/skills")
def assessment_skills(db: Session = Depends(get_db)):
    counts = (
        db.query(models.Skill.id, models.Skill.name, func.count(models.AssessmentQuestion.id))
        .join(models.AssessmentQuestion, models.Skill.id == models.AssessmentQuestion.skill_id)
        .group_by(models.Skill.id, models.Skill.name)
        .order_by(models.Skill.name)
        .all()
    )
    return [{"id": sid, "name": name, "question_count": n} for sid, name, n in counts]


@router.get("/questions/{skill_id}")
def questions(skill_id: int, limit: int = 10, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.AssessmentQuestion).where(models.AssessmentQuestion.skill_id == skill_id).limit(min(limit, 30))
    ).all()
    if not rows:
        raise HTTPException(404, "No assessment questions available for this skill yet.")
    # Correct answers and explanations are deliberately NOT included.
    return [
        {
            "id": q.id,
            "question": q.question,
            "options": {"A": q.option_a, "B": q.option_b, "C": q.option_c, "D": q.option_d},
            "difficulty": q.difficulty,
        }
        for q in rows
    ]


@router.post("/submit")
def submit_assessment(payload: dict, user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    skill_id = int(payload.get("skill_id", 0))
    answers = payload.get("answers", {})
    rows = db.scalars(select(models.AssessmentQuestion).where(models.AssessmentQuestion.skill_id == skill_id)).all()
    if not rows:
        raise HTTPException(404, "Assessment skill not found")
    correct = sum(1 for q in rows if answers.get(str(q.id)) == q.correct_option)
    pct = round(correct / len(rows) * 100, 2)
    attempt = models.AssessmentAttempt(
        user_id=user.id,
        skill_id=skill_id,
        total_questions=len(rows),
        correct_answers=correct,
        score_percent=pct,
        answers_json=json.dumps(answers),
    )
    db.add(attempt)
    level = estimate_level(pct)
    current = db.scalar(
        select(models.StudentSkill).where(
            models.StudentSkill.user_id == user.id, models.StudentSkill.skill_id == skill_id
        )
    )
    if current:
        current.level = level
    else:
        db.add(models.StudentSkill(user_id=user.id, skill_id=skill_id, level=level))
    db.commit()
    review = [
        {
            "question_id": q.id,
            "correct_option": q.correct_option,
            "your_answer": answers.get(str(q.id)),
            "is_correct": answers.get(str(q.id)) == q.correct_option,
            "explanation": q.explanation,
        }
        for q in rows
    ]
    return {
        "attempt_id": attempt.id,
        "correct": correct,
        "total": len(rows),
        "score_percent": pct,
        "estimated_level": level,
        "review": review,
    }


@router.get("/history")
def history(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == user.id)
        .order_by(models.AssessmentAttempt.created_at.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": a.id,
            "skill": skill_name,
            "score_percent": a.score_percent,
            "correct": a.correct_answers,
            "total": a.total_questions,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, skill_name in rows
    ]
