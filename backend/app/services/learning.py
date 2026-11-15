"""Learning resources and personalised learning paths (rule-based).

Path rules:
* Steps are the target career's skills that are not yet met, ordered like the gap
  analysis (critical first, then by importance weight). Met skills are listed as done.
* Resource difficulty follows the student's ASSESSED level for that skill:
  not assessed or level 1-2 -> beginner, 3 -> intermediate, 4-5 -> advanced
  (closest difficulty first; resources already completed are skipped).
* Step status: done (requirement met), not_assessed (take the assessment first),
  in_progress (a resource is in progress), ready_to_reassess (all suggested
  resources completed), or todo.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.services.career import gap_analysis

RESOURCE_FILE = Path(__file__).resolve().parents[1] / "learning_resources.json"
RESOURCE_TYPES = ("documentation", "course", "tutorial", "practice", "project", "book", "video", "certification")
LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def load_resources(db: Session, path: Path = RESOURCE_FILE) -> int:
    """Insert bundled resources that are missing (matched by skill + title). Never edits or deletes rows."""
    data = json.loads(path.read_text(encoding="utf-8"))["skills"]
    skills = {s.name: s.id for s in db.scalars(select(models.Skill))}
    existing = set(db.execute(select(models.LearningResource.skill_id, models.LearningResource.title)).all())
    added = 0
    for skill, rows in data.items():
        if skill not in skills:
            raise ValueError(f"learning_resources.json: unknown skill '{skill}'")
        for r in rows:
            if r["type"] not in RESOURCE_TYPES or r["difficulty"] not in LEVEL_ORDER:
                raise ValueError(f"learning_resources.json: invalid type/difficulty for '{r['title']}'")
            if (skills[skill], r["title"]) in existing:
                continue
            db.add(models.LearningResource(
                skill_id=skills[skill], title=r["title"], provider=r["provider"], url=r["url"],
                resource_type=r["type"], difficulty=r["difficulty"], description=r["description"],
                is_free=r.get("is_free", True), estimated_hours=r.get("estimated_hours"),
            ))
            existing.add((skills[skill], r["title"]))
            added += 1
    db.flush()
    return added


def target_difficulty(level: int | None) -> str:
    if not level or level <= 2:
        return "beginner"
    return "intermediate" if level == 3 else "advanced"


def progress_by_resource(db: Session, user_id: int) -> dict[int, models.LearningProgress]:
    return {p.resource_id: p for p in db.scalars(select(models.LearningProgress).where(models.LearningProgress.user_id == user_id))}


def resource_out(r: models.LearningResource, skill_name: str, p: models.LearningProgress | None) -> dict:
    return {
        "id": r.id, "skill_id": r.skill_id, "skill": skill_name, "title": r.title, "provider": r.provider,
        "url": r.url, "type": r.resource_type, "difficulty": r.difficulty, "description": r.description,
        "is_free": r.is_free, "estimated_hours": r.estimated_hours,
        "status": p.status if p else "not_started", "notes": p.notes if p else "",
        "started_at": p.started_at if p else None, "completed_at": p.completed_at if p else None,
    }


def learning_path(db: Session, user: models.User, career: models.CareerRole, per_step: int = 3) -> dict:
    gaps = gap_analysis(db, career, user.id)
    progress = progress_by_resource(db, user.id)
    by_skill: dict[int, list[models.LearningResource]] = {}
    for r in db.scalars(select(models.LearningResource).where(
            models.LearningResource.skill_id.in_([s["skill_id"] for s in gaps["skills"]] or [-1]))):
        by_skill.setdefault(r.skill_id, []).append(r)

    steps, done = [], []
    for s in gaps["skills"]:
        if s["status"] == "meets":
            done.append({"skill_id": s["skill_id"], "skill": s["skill"], "status": "done",
                         "current_level": s["current_level"], "required_level": s["required_level"]})
            continue
        want = target_difficulty(s["current_level"] if s["assessed"] else None)
        pool = sorted(by_skill.get(s["skill_id"], []),
                      key=lambda r: (abs(LEVEL_ORDER[r.difficulty] - LEVEL_ORDER[want]), r.title))
        open_ = [r for r in pool if (progress.get(r.id) and progress[r.id].status) != "completed"]
        picks = open_[:per_step]
        completed = [r for r in pool if progress.get(r.id) and progress[r.id].status == "completed"]
        if not s["assessed"]:
            status = "not_assessed"
        elif any(progress.get(r.id) and progress[r.id].status == "in_progress" for r in pool):
            status = "in_progress"
        elif pool and not open_:
            status = "ready_to_reassess"
        else:
            status = "todo"
        steps.append({
            "step": len(steps) + 1, "skill_id": s["skill_id"], "skill": s["skill"], "status": status,
            "gap_status": s["status"], "assessed": s["assessed"], "current_level": s["current_level"],
            "required_level": s["required_level"], "importance": s["importance"], "target_difficulty": want,
            "resources": [resource_out(r, s["skill"], progress.get(r.id)) for r in picks],
            "completed_resources": len(completed),
            "action": ("Take the assessment to set your starting level, then begin with these resources."
                       if not s["assessed"] else
                       "All suggested resources completed: reassess to update your level."
                       if status == "ready_to_reassess" else
                       f"Work toward level {s['required_level']} (you are at {s['current_level']})."),
        })
    return {
        "career_id": career.id, "career": career.name, "alignment_score": gaps["alignment_score"],
        "rules": __doc__.split("Path rules:")[1].strip(),
        "steps": steps, "completed_skills": done,
        "totals": {"steps": len(steps), "skills_met": len(done),
                   "resources_completed": sum(st["completed_resources"] for st in steps)},
    }


def load_career(db: Session, career_id: int) -> models.CareerRole | None:
    return db.scalar(select(models.CareerRole)
                     .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
                     .where(models.CareerRole.id == career_id))
