"""Question bank management for teachers and administrators.

Questions are never hard-deleted: deactivate them instead. Past attempts keep
their own snapshot, so edits never change historical results.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.deps import require_staff
from app.schemas import AssessmentQuestionCreate, AssessmentQuestionUpdate
from app.services.audit import audit

router = APIRouter(prefix="/question-bank", tags=["question bank"])
FIELDS = ["question", "option_a", "option_b", "option_c", "option_d", "correct_option", "explanation",
          "difficulty", "topic", "subtopic", "is_active"]


def _out(q: models.AssessmentQuestion, skill_name: str) -> dict:
    return {"id": q.id, "skill_id": q.skill_id, "skill": skill_name, **{f: getattr(q, f) for f in FIELDS},
            "source": "bundled" if q.bank_key else "staff", "updated_at": q.updated_at}


def _check(db: Session, skill_id: int, data: dict, exclude_id: int | None = None) -> None:
    opts = [data[k].strip() for k in ("option_a", "option_b", "option_c", "option_d")]  # case-sensitive
    if len(set(opts)) != 4:
        raise HTTPException(422, "The four options must be different")
    text = " ".join(data["question"].split()).lower()
    clash = db.scalar(select(models.AssessmentQuestion.id).where(
        models.AssessmentQuestion.skill_id == skill_id,
        func.lower(models.AssessmentQuestion.question) == text,
        models.AssessmentQuestion.id != (exclude_id or -1)))
    if clash:
        raise HTTPException(409, "This skill already has a question with the same text")


@router.get("/questions")
def list_questions(skill_id: int | None = None, difficulty: str | None = None, active: bool | None = None,
                   search: str | None = None, page: int = 1, page_size: int = 25,
                   _: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    page, page_size = max(page, 1), min(max(page_size, 1), 100)
    stmt = select(models.AssessmentQuestion, models.Skill.name).join(
        models.Skill, models.Skill.id == models.AssessmentQuestion.skill_id)
    if skill_id:
        stmt = stmt.where(models.AssessmentQuestion.skill_id == skill_id)
    if difficulty:
        stmt = stmt.where(models.AssessmentQuestion.difficulty == difficulty)
    if active is not None:
        stmt = stmt.where(models.AssessmentQuestion.is_active.is_(active))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(models.AssessmentQuestion.question.ilike(like) | models.AssessmentQuestion.topic.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(models.Skill.name, models.AssessmentQuestion.difficulty,
                                    models.AssessmentQuestion.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_out(q, n) for q, n in rows], "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size}


@router.post("/questions", status_code=201)
def create_question(body: AssessmentQuestionCreate, request: Request, user: models.User = Depends(require_staff),
                    db: Session = Depends(get_db)):
    skill = db.get(models.Skill, body.skill_id)
    if skill is None:
        raise HTTPException(422, "Unknown skill")
    data = body.model_dump()
    _check(db, body.skill_id, data)
    q = models.AssessmentQuestion(**{k: data[k] for k in ["skill_id", *FIELDS]}, created_by=user.id)
    db.add(q)
    db.flush()
    audit(db, "question.created", user_id=user.id, entity_type="assessment_question", entity_id=q.id, request=request)
    db.commit()
    return _out(q, skill.name)


@router.put("/questions/{question_id}")
def update_question(question_id: int, body: AssessmentQuestionUpdate, request: Request,
                    user: models.User = Depends(require_staff), db: Session = Depends(get_db)):
    q = db.get(models.AssessmentQuestion, question_id)
    if q is None:
        raise HTTPException(404, "Question not found")
    changes = body.model_dump(exclude_unset=True)
    merged = {f: changes.get(f, getattr(q, f)) for f in FIELDS}
    _check(db, q.skill_id, merged, exclude_id=q.id)
    for k, v in changes.items():
        setattr(q, k, v)
    audit(db, "question.updated", user_id=user.id, entity_type="assessment_question", entity_id=q.id,
          details={"fields": sorted(changes)}, request=request)
    db.commit()
    return _out(q, db.get(models.Skill, q.skill_id).name)
