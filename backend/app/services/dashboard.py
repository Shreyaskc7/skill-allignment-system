"""Student dashboard: every number comes from the student's own database records."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.services.alignment import career_alignment
from app.services.profile import completion, get_or_create_profile

PRIORITY_ORDER = {"High": 0, "Medium": 1, "On track": 2}


def student_dashboard(db: Session, user: models.User) -> dict:
    profile = get_or_create_profile(db, user)

    # Assessed proficiency (evidence from submitted assessments only).
    assessed = db.execute(
        select(models.StudentSkill, models.Skill)
        .join(models.Skill, models.Skill.id == models.StudentSkill.skill_id)
        .where(models.StudentSkill.user_id == user.id)
        .order_by(models.StudentSkill.level.desc(), models.Skill.name)
    ).all()
    levels = {s.skill_id: s.level for s, _ in assessed}

    # Assessment performance
    attempts = db.execute(
        select(models.AssessmentAttempt, models.Skill.name)
        .join(models.Skill, models.Skill.id == models.AssessmentAttempt.skill_id)
        .where(models.AssessmentAttempt.user_id == user.id, models.AssessmentAttempt.status == "submitted")
        .order_by(models.AssessmentAttempt.created_at.desc(), models.AssessmentAttempt.id.desc())
    ).all()
    scores = [a.score_percent for a, _ in attempts]

    # Target career alignment (same weighted formula as the Skill Gaps page)
    career_block = None
    gap_skill_ids: list[int] = []
    if profile.target_career_id:
        role = db.scalar(
            select(models.CareerRole)
            .options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill))
            .where(models.CareerRole.id == profile.target_career_id)
        )
        if role:
            score, rows = career_alignment(role.skills, levels)
            missing = sorted((r for r in rows if r["gap"] > 0), key=lambda r: (PRIORITY_ORDER[r["priority"]], -r["importance"]))
            gap_skill_ids = [r["skill_id"] for r in missing]
            career_block = {
                "id": role.id,
                "name": role.name,
                "alignment_score": score,
                "skills_met": sum(1 for r in rows if r["gap"] == 0),
                "skills_total": len(rows),
                "missing_skills": [
                    {k: r[k] for k in ("skill_id", "skill", "current_level", "required_level", "importance", "priority")}
                    | {"assessed": r["skill_id"] in levels}
                    for r in missing
                ],
            }

    # Learning progress
    progress = db.execute(
        select(models.LearningProgress, models.LearningResource.title)
        .join(models.LearningResource, models.LearningResource.id == models.LearningProgress.resource_id)
        .where(models.LearningProgress.user_id == user.id)
        .order_by(models.LearningProgress.updated_at.desc())
    ).all()
    status_of = {p.resource_id: p.status for p, _ in progress}

    # Recommended resources: for the target career's gap skills, highest priority first, not completed.
    recommended = []
    if gap_skill_ids:
        res = db.execute(
            select(models.LearningResource, models.Skill.name)
            .join(models.Skill, models.Skill.id == models.LearningResource.skill_id)
            .where(models.LearningResource.skill_id.in_(gap_skill_ids))
        ).all()
        rank = {sid: i for i, sid in enumerate(gap_skill_ids)}
        for r, skill in sorted(res, key=lambda x: (rank[x[0].skill_id], x[0].title)):
            if status_of.get(r.id) != "completed":
                recommended.append({
                    "id": r.id, "title": r.title, "skill": skill, "provider": r.provider, "url": r.url,
                    "type": r.resource_type, "status": status_of.get(r.id, "not_started"),
                })
        recommended = recommended[:5]

    # Recent activity: latest attempts and learning updates, merged by time.
    activity = [
        {"type": "assessment", "text": f"Completed {skill} assessment ({a.score_percent:g}%)", "at": a.created_at}
        for a, skill in attempts[:5]
    ] + [
        {"type": "learning", "text": f"Marked “{title}” as {p.status.replace('_', ' ')}", "at": p.updated_at}
        for p, title in progress[:5]
    ]
    activity = sorted((x for x in activity if x["at"]), key=lambda x: x["at"], reverse=True)[:6]

    return {
        "user": {"full_name": user.full_name, "email": user.email},
        "profile_completion": completion(db, profile),
        "target_career": career_block,
        "assessed_skills": [
            {"skill_id": s.skill_id, "skill": sk.name, "level": s.level, "updated_at": s.updated_at}
            for s, sk in assessed
        ],
        "self_reported_skill_count": db.scalar(
            select(func.count(models.StudentSelfSkill.id)).where(models.StudentSelfSkill.user_id == user.id)
        ),
        "assessments": {
            "count": len(attempts),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "best_score": max(scores) if scores else None,
            "latest": [
                {"skill": skill, "score_percent": a.score_percent, "created_at": a.created_at}
                for a, skill in attempts[:5]
            ],
        },
        "learning": {
            "completed": sum(p.status == "completed" for p, _ in progress),
            "in_progress": sum(p.status == "in_progress" for p, _ in progress),
            "tracked": len(progress),
        },
        "recommended_resources": recommended,
        # Job matching is implemented in Phase 8; nothing is shown until then (never fabricated).
        "matching_jobs": {"available": False, "reason": "Job matching becomes available in a later release."},
        "recent_activity": activity,
    }
