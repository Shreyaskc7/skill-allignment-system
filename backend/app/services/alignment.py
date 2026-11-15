"""Assessment level estimate and weighted career alignment (rule-based, not ML).

Business logic preserved verbatim from version 1.
"""


def estimate_level(score_percent: float) -> int:
    """Map an assessment score to a 1-5 proficiency level.

    ``round`` is Python's round-half-to-even, so exact .5 cases round to the
    even level: 10% -> 1, 30% -> 2, 50% -> 2, 70% -> 4, 90% -> 4. A 0% score
    still yields level 1. Kept unchanged in Phase 2; revisited in Phase 6.
    """
    return max(1, min(5, round(score_percent / 20)))


def gap_priority(required: int, level: int, weight: int) -> str:
    if required - level >= 2 and weight >= 4:
        return "High"
    return "Medium" if required > level else "On track"


def career_alignment(requirements, levels: dict[int, int]) -> tuple[int, list[dict]]:
    """Weighted alignment of a student's skill levels against a role.

    alignment = sum(min(level, required) / required * weight) / sum(weight) * 100

    ``requirements`` are CareerRoleSkill rows (with ``.skill`` loaded);
    ``levels`` maps skill_id -> current level. Unassessed skills count as 0.
    """
    rows, weighted, total = [], 0.0, 0
    for link in requirements:
        level = levels.get(link.skill_id, 0)
        weight = link.importance_weight
        weighted += min(level, link.required_level) / max(link.required_level, 1) * weight
        total += weight
        rows.append(
            {
                "skill_id": link.skill_id,
                "skill": link.skill.name,
                "current_level": level,
                "required_level": link.required_level,
                "importance": weight,
                "gap": max(0, link.required_level - level),
                "priority": gap_priority(link.required_level, level, weight),
            }
        )
    return (round(weighted / total * 100) if total else 0), rows
