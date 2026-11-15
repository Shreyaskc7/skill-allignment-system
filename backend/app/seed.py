"""Idempotent seeding of the demo student and the starter catalogue."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.security import hash_password
from app.seed_data import CATALOG, QUESTIONS, RESOURCES, ROLE_SKILLS
from app.services.current_user import DEMO_STUDENT_EMAIL


def seed(db: Session) -> None:
    user = db.scalar(select(models.User).where(models.User.email == DEMO_STUDENT_EMAIL))
    if not user:
        # The demo student cannot log in: its password is a random, discarded value.
        user = models.User(
            email=DEMO_STUDENT_EMAIL,
            full_name="Student Demo",
            role=models.UserRole.student,
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)

    for name, (cat, desc) in CATALOG.items():
        if not db.scalar(select(models.Skill).where(models.Skill.name == name)):
            db.add(models.Skill(name=name, category=cat, description=desc))
    db.flush()

    for role, entries in ROLE_SKILLS.items():
        obj = db.scalar(select(models.CareerRole).where(models.CareerRole.name == role))
        if not obj:
            obj = models.CareerRole(
                name=role,
                description=f"Skills and competencies commonly associated with a {role.lower()} role.",
            )
            db.add(obj)
            db.flush()
        for skill, level, weight in entries:
            sk = db.scalar(select(models.Skill).where(models.Skill.name == skill))
            if sk and not db.scalar(
                select(models.CareerRoleSkill).where(
                    models.CareerRoleSkill.career_role_id == obj.id,
                    models.CareerRoleSkill.skill_id == sk.id,
                )
            ):
                db.add(
                    models.CareerRoleSkill(
                        career_role_id=obj.id, skill_id=sk.id, required_level=level, importance_weight=weight
                    )
                )
    db.flush()

    for skill, qs in QUESTIONS.items():
        sk = db.scalar(select(models.Skill).where(models.Skill.name == skill))
        for q, opts, correct, explain, diff in qs:
            if not db.scalar(
                select(models.AssessmentQuestion).where(
                    models.AssessmentQuestion.skill_id == sk.id, models.AssessmentQuestion.question == q
                )
            ):
                db.add(
                    models.AssessmentQuestion(
                        skill_id=sk.id,
                        question=q,
                        option_a=opts[0],
                        option_b=opts[1],
                        option_c=opts[2],
                        option_d=opts[3],
                        correct_option=correct,
                        explanation=explain,
                        difficulty=diff,
                    )
                )
    db.flush()

    for skill, items in RESOURCES.items():
        sk = db.scalar(select(models.Skill).where(models.Skill.name == skill))
        for title, provider, url, typ, diff, desc in items:
            if not db.scalar(
                select(models.LearningResource).where(
                    models.LearningResource.skill_id == sk.id, models.LearningResource.title == title
                )
            ):
                db.add(
                    models.LearningResource(
                        skill_id=sk.id,
                        title=title,
                        provider=provider,
                        url=url,
                        resource_type=typ,
                        difficulty=diff,
                        description=desc,
                        is_free=True,
                    )
                )
    db.commit()
