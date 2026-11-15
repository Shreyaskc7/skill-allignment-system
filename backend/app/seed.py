"""Idempotent seeding of the starter catalogue (skills, roles, questions, resources).

No user accounts are seeded: create the first administrator with `python -m app.cli create-admin`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.seed_data import CATALOG, ROLE_SKILLS
from app.services.question_bank import load_question_bank
from app.services.learning import load_resources
from app.services.skill_extraction import seed_aliases


def seed(db: Session) -> None:
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

    # Assessment questions come from app/question_bank/*.json (Phase 6).
    load_question_bank(db)
    seed_aliases(db)

    # Learning resources come from app/learning_resources.json (Phase 9, links verified).
    load_resources(db)
    db.commit()
