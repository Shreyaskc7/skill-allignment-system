"""Skill assessments: attempt-based delivery, submission, results and history.

Replaces the version 1 endpoints (`GET /questions/{skill_id}`, `POST /submit`),
which scored every question of a skill rather than the ones delivered.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import get_current_user, require_student
from app.services import assessment as svc

router = APIRouter(prefix="/assessments", tags=["assessments"])


class StartAttempt(BaseModel):
    skill_id: int
    question_count: int = Field(10, ge=svc.MIN_QUESTIONS, le=svc.MAX_QUESTIONS)
    difficulty: Literal["mixed", "beginner", "intermediate", "advanced"] = "mixed"
    timed: bool = False
    restart: bool = False


class Answer(BaseModel):
    question_id: int
    answer: Literal["A", "B", "C", "D"]


class SubmitAttempt(BaseModel):
    answers: list[Answer] = Field(max_length=svc.MAX_QUESTIONS)


@router.get("/skills", dependencies=[Depends(get_current_user)])
def assessment_skills(db: Session = Depends(get_db)):
    """Skills with at least 5 active questions, with counts per difficulty."""
    return svc.available_skills(db)


@router.post("/attempts", status_code=201)
def start(body: StartAttempt, user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    attempt, resumed = svc.start_attempt(db, user, body.skill_id, body.question_count, body.difficulty, body.timed,
                                         body.restart)
    db.commit()
    db.refresh(attempt)
    return svc.delivery(attempt, resumed)


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: int, user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = svc.owned_attempt(db, user, attempt_id)
    if svc.expire_if_needed(db, attempt):
        db.commit()
    if attempt.status == "in_progress":
        return svc.delivery(attempt, resumed=True)
    if attempt.status == "submitted":
        return svc.result(attempt)
    raise HTTPException(409, f"This attempt was {attempt.status} and has no result.")


@router.post("/attempts/{attempt_id}/submit")
def submit(attempt_id: int, body: SubmitAttempt, user: models.User = Depends(require_student),
           db: Session = Depends(get_db)):
    attempt = svc.submit_attempt(db, user, attempt_id, [(a.question_id, a.answer) for a in body.answers])
    db.commit()
    return svc.result(attempt)


@router.get("/history")
def history(user: models.User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == user.id, svc.submitted_only())
        .order_by(models.AssessmentAttempt.created_at.desc(), models.AssessmentAttempt.id.desc())
        .limit(100)
    ).all()
    return [
        {"id": a.id, "skill": name, "score_percent": a.score_percent, "correct": a.correct_answers,
         "total": a.total_questions, "estimated_level": a.estimated_level, "difficulty": a.difficulty,
         "created_at": (a.submitted_at or a.created_at).isoformat() if (a.submitted_at or a.created_at) else None}
        for a, name in rows
    ]
