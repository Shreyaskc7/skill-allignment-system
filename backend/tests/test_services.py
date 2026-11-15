"""Unit tests for pure business logic (no database needed)."""

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.alignment import career_alignment, estimate_level, gap_priority
from app.services.skill_extraction import extract_skills


def req(skill_id, name, required, weight):
    return SimpleNamespace(
        skill_id=skill_id, skill=SimpleNamespace(name=name), required_level=required, importance_weight=weight
    )


def test_alignment_matches_hand_calculation():
    reqs = [req(1, "Python", 4, 5), req(2, "SQL", 4, 4), req(3, "Git", 3, 3)]
    # Python 2/4*5 = 2.5 ; SQL capped 4/4*4 = 4 ; Git unassessed 0 -> 6.5 / 12 = 54.17% -> 54
    score, rows = career_alignment(reqs, {1: 2, 2: 5})
    assert score == 54
    assert [r["current_level"] for r in rows] == [2, 5, 0]
    assert [r["gap"] for r in rows] == [2, 0, 3]
    assert [r["priority"] for r in rows] == ["High", "On track", "Medium"]


def test_alignment_edge_cases():
    assert career_alignment([], {}) == (0, [])
    assert career_alignment([req(1, "X", 3, 2)], {1: 3})[0] == 100
    assert career_alignment([req(1, "X", 3, 2)], {})[0] == 0


@pytest.mark.parametrize(
    "pct,level",
    [(0, 1), (10, 1), (19.99, 1), (20, 2), (39.9, 2), (40, 3), (50, 3), (60, 4), (70, 4), (79.99, 4), (80, 5),
     (90, 5), (100, 5), (66.67, 4), (-5, 1), (120, 5)],
)
def test_estimate_level_uses_equal_bands(pct, level):
    # Phase 6 correction of the v1 round-half-to-even mapping (90% used to give 4).
    assert estimate_level(pct) == level


def test_gap_priority_rules():
    assert gap_priority(required=4, level=2, weight=4) == "High"
    assert gap_priority(required=4, level=2, weight=3) == "Medium"
    assert gap_priority(required=4, level=4, weight=5) == "On track"


def test_extract_skills_aliases_and_boundaries():
    text = "Need JS, postgres and PowerBI; data analytics. Javascript expert. Not 'gitlab' or 'csss'."
    found = extract_skills(text)
    assert {"JavaScript", "PostgreSQL", "Power BI", "Data Analysis"} <= set(found)
    assert "Git" not in found and "CSS" not in found
    assert found == sorted(set(found))


def test_cors_origins_merge_and_dedupe():
    s = Settings(frontend_origin="http://a:1/", frontend_origins="http://b:2, http://a:1 ,,http://c:3/")
    assert s.cors_origins == ["http://a:1", "http://b:2", "http://c:3"]
