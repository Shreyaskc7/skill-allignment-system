"""Explainable skill-gap analysis and rule-based career recommendations.

Everything here is RULE-BASED (no machine learning). The alignment score is the
unchanged version 1 weighted formula from ``services.alignment.career_alignment``:

    alignment = sum(min(level, required) / required * weight) / sum(weight) * 100

This module only explains it (per-skill contribution, status, next steps) and ranks
career roles by it. Scores are guidance, never a probability of being hired.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.services.alignment import career_alignment

FORMULA = "alignment = Σ(min(assessed level, required level) / required level × weight) / Σ weight × 100"
STOPWORDS = {"and", "or", "the", "a", "an", "of", "in", "to", "for", "with", "role", "roles", "skills",
             "commonly", "associated", "competencies", "developer", "engineer"}


def student_evidence(db: Session, user_id: int) -> tuple[dict[int, models.StudentSkill], dict[int, int]]:
    """(assessed StudentSkill rows by skill id, self-reported levels by skill id)."""
    assessed = {s.skill_id: s for s in db.scalars(select(models.StudentSkill).where(models.StudentSkill.user_id == user_id))}
    claimed = dict(db.execute(
        select(models.StudentSelfSkill.skill_id, models.StudentSelfSkill.level)
        .where(models.StudentSelfSkill.user_id == user_id)).all())
    return assessed, claimed


def gap_analysis(db: Session, role: models.CareerRole, user_id: int) -> dict:
    assessed, claimed = student_evidence(db, user_id)
    levels = {sid: s.level for sid, s in assessed.items()}
    score, rows = career_alignment(role.skills, levels)  # unchanged formula
    total_weight = sum(r["importance"] for r in rows) or 1

    items = []
    for r in rows:
        ev = assessed.get(r["skill_id"])
        earned = min(r["current_level"], r["required_level"]) / max(r["required_level"], 1) * r["importance"]
        if r["gap"] == 0:
            status = "meets"
        elif r["priority"] == "High":
            status = "critical"
        else:
            status = "needs_improvement"
        items.append({
            **r,
            "assessed": ev is not None,
            "status": status,
            "last_assessed_at": ev.last_assessed_at if ev else None,
            "evidence_attempt_id": ev.evidence_attempt_id if ev else None,
            "self_reported_level": claimed.get(r["skill_id"]),
            # Contribution in score points: earned / Σweight × 100 (sums to the alignment score before rounding)
            "contribution": round(earned / total_weight * 100, 1),
            "max_contribution": round(r["importance"] / total_weight * 100, 1),
        })

    order = {"critical": 0, "needs_improvement": 1, "meets": 2}
    items.sort(key=lambda x: (order[x["status"]], -x["importance"], x["skill"]))
    return {
        "career_id": role.id,
        "career": role.name,
        "description": role.description,
        "alignment_score": score,
        "formula": FORMULA,
        "summary": {
            "meets": sum(i["status"] == "meets" for i in items),
            "needs_improvement": sum(i["status"] == "needs_improvement" for i in items),
            "critical": sum(i["status"] == "critical" for i in items),
            "unassessed": sum(not i["assessed"] for i in items),
            "total": len(items),
        },
        "skills": items,
        "next_steps": next_steps(db, user_id, items),
    }


def next_steps(db: Session, user_id: int, items: list[dict], limit: int = 4) -> list[dict]:
    """Concrete actions for the highest-priority gaps: assess first, then learn."""
    gaps = [i for i in items if i["status"] != "meets"]
    if not gaps:
        return [{"type": "done", "text": "You meet every requirement for this role. Keep your skills current."}]
    completed = set(db.scalars(select(models.LearningProgress.resource_id).where(
        models.LearningProgress.user_id == user_id, models.LearningProgress.status == "completed")))
    steps = []
    for g in gaps:
        if len(steps) >= limit:
            break
        if not g["assessed"]:
            steps.append({"type": "assess", "skill_id": g["skill_id"], "skill": g["skill"],
                          "text": f"Take the {g['skill']} assessment to measure your current level."})
            continue
        res = db.scalar(select(models.LearningResource).where(
            models.LearningResource.skill_id == g["skill_id"], models.LearningResource.id.notin_(completed or [-1]))
            .order_by(models.LearningResource.difficulty, models.LearningResource.title))
        text = (f"Raise {g['skill']} from level {g['current_level']} to {g['required_level']}"
                + (f": start with “{res.title}” ({res.provider})." if res else ", then reassess."))
        steps.append({"type": "learn", "skill_id": g["skill_id"], "skill": g["skill"], "text": text,
                      "resource": None if res is None else {"id": res.id, "title": res.title, "url": res.url}})
    return steps


def _words(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z+#]{2,}", (text or "").lower()) if w not in STOPWORDS}


def recommendations(db: Session, user: models.User) -> dict:
    """Rank active roles by alignment; stated interests only break ties and are shown as reasons."""
    profile = db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == user.id))
    interest_text = " ".join(filter(None, [profile and profile.career_interests, profile and profile.target_job_roles]))
    interests = _words(interest_text)
    target_id = profile.target_career_id if profile else None
    assessed, claimed = student_evidence(db, user.id)
    levels = {sid: s.level for sid, s in assessed.items()}

    roles = db.scalars(
        select(models.CareerRole).where(models.CareerRole.is_active.is_(True))
        .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
    ).all()
    out = []
    for role in roles:
        score, rows = career_alignment(role.skills, levels)
        role_words = _words(role.name) | _words(role.description) | {w for r in rows for w in _words(r["skill"])}
        interest_hits = sorted(interests & role_words)
        matching = [r["skill"] for r in rows if r["gap"] == 0]
        to_improve = [r["skill"] for r in rows if r["gap"] > 0 and r["skill_id"] in levels]
        missing = [r["skill"] for r in rows if r["skill_id"] not in levels]
        claimed_relevant = [r["skill"] for r in rows if r["skill_id"] in claimed and r["skill_id"] not in levels]
        reasons = []
        if matching:
            reasons.append(f"You already meet {len(matching)} of {len(rows)} required skills.")
        if interest_hits:
            reasons.append(f"Matches your stated interests: {', '.join(interest_hits)}.")
        if claimed_relevant:
            reasons.append(f"You reported {', '.join(claimed_relevant)}; take those assessments to count them.")
        out.append({
            "career_id": role.id,
            "career": role.name,
            "description": role.description,
            "alignment_score": score,
            "is_target": role.id == target_id,
            "interest_match": interest_hits,
            "matching_skills": matching,
            "skills_to_improve": to_improve,
            "missing_skills": missing,
            "required_skills": [{"skill": r["skill"], "required_level": r["required_level"], "weight": r["importance"],
                                 "current_level": r["current_level"]} for r in rows],
            "reasons": reasons,
        })
    out.sort(key=lambda r: (-r["alignment_score"], -len(r["interest_match"]), r["career"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return {
        "method": "Ranked by the rule-based weighted alignment score; stated interests break ties only. "
                  "Scores are guidance, not a prediction of being hired.",
        "assessed_skill_count": len(levels),
        "recommendations": out,
    }
