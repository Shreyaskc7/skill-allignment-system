"""Student profile helpers: completion and lazy profile creation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models

# Fields that count toward profile completion (resume is optional and excluded).
COMPLETION_FIELDS = [
    ("phone", "Phone number"),
    ("location", "Location"),
    ("college", "College / institution"),
    ("degree", "Degree"),
    ("department", "Department"),
    ("specialization", "Specialization"),
    ("current_semester", "Current semester"),
    ("graduation_year", "Graduation year"),
    ("career_interests", "Career interests"),
    ("preferred_locations", "Preferred job locations"),
    ("experience_level", "Experience level"),
    ("target_career_id", "Target career"),
    ("profile_image_url", "Profile photo"),
]


def get_or_create_profile(db: Session, user: models.User) -> models.StudentProfile:
    profile = db.scalar(select(models.StudentProfile).where(models.StudentProfile.user_id == user.id))
    if profile is None:  # e.g. accounts created before profiles existed
        profile = models.StudentProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def completion(db: Session, profile: models.StudentProfile) -> dict:
    missing = [label for field, label in COMPLETION_FIELDS if getattr(profile, field) in (None, "")]
    has_skills = bool(
        db.scalar(select(func.count(models.StudentSelfSkill.id)).where(models.StudentSelfSkill.user_id == profile.user_id))
    )
    if not has_skills:
        missing.append("Skills and interests")
    total = len(COMPLETION_FIELDS) + 1
    return {"percent": round((total - len(missing)) / total * 100), "missing": missing}
