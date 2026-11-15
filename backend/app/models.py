"""SQLAlchemy models for the SkillAlign application."""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Float,
    func,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class UserRole(PyEnum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.student)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    student_profile: Mapped["StudentProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher_profile: Mapped["TeacherProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    assessment_attempts: Mapped[list["AssessmentAttempt"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    student_skills: Mapped[list["StudentSkill"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    learning_progress: Mapped[list["LearningProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mentoring_notes: Mapped[list["MentoringNote"]] = relationship("MentoringNote", foreign_keys="MentoringNote.teacher_id", back_populates="teacher", cascade="all, delete-orphan")
    student_assignments: Mapped[list["StudentTeacherAssignment"]] = relationship("StudentTeacherAssignment", foreign_keys="StudentTeacherAssignment.student_id", back_populates="student", cascade="all, delete-orphan")
    teacher_assignments: Mapped[list["StudentTeacherAssignment"]] = relationship("StudentTeacherAssignment", foreign_keys="StudentTeacherAssignment.teacher_id", back_populates="teacher", cascade="all, delete-orphan")


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Personal details
    phone: Mapped[str | None] = mapped_column(String(30))
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(160))
    profile_image_url: Mapped[str | None] = mapped_column(String(500))

    # Academic details
    college: Mapped[str | None] = mapped_column(String(200))
    degree: Mapped[str | None] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120))
    specialization: Mapped[str | None] = mapped_column(String(120))
    current_semester: Mapped[int | None] = mapped_column(Integer)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    cgpa: Mapped[float | None] = mapped_column(Float)

    # Career details
    career_interests: Mapped[str | None] = mapped_column(Text)
    target_job_roles: Mapped[str | None] = mapped_column(Text)
    technical_skills: Mapped[str | None] = mapped_column(Text)
    soft_skills: Mapped[str | None] = mapped_column(Text)
    preferred_locations: Mapped[str | None] = mapped_column(Text)
    experience_level: Mapped[str | None] = mapped_column(String(60))
    resume_url: Mapped[str | None] = mapped_column(String(500))
    # Selected target career (drives the dashboard alignment and recommendations).
    target_career_id: Mapped[int | None] = mapped_column(ForeignKey("career_roles.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="student_profile")


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Personal details
    phone: Mapped[str | None] = mapped_column(String(30))
    profile_image_url: Mapped[str | None] = mapped_column(String(500))

    # Professional details
    qualification: Mapped[str | None] = mapped_column(String(200))
    institution: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    designation: Mapped[str | None] = mapped_column(String(120))
    specialization: Mapped[str | None] = mapped_column(String(160))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    areas_of_expertise: Mapped[str | None] = mapped_column(Text)
    biography: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="teacher_profile")


class StudentTeacherAssignment(Base):
    __tablename__ = "student_teacher_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # At most one ACTIVE assignment per student/teacher pair; any number of
        # inactive (historical) rows are allowed.
        Index(
            "uq_active_assignment_pair",
            "student_id",
            "teacher_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
    )

    student: Mapped["User"] = relationship(foreign_keys=[student_id], back_populates="student_assignments")
    teacher: Mapped["User"] = relationship(foreign_keys=[teacher_id], back_populates="teacher_assignments")


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="technical")
    description: Mapped[str | None] = mapped_column(Text)
    # ESCO integration (optional)
    esco_identifier: Mapped[str | None] = mapped_column(String(50))
    esco_label: Mapped[str | None] = mapped_column(String(200))

    role_links: Mapped[list["CareerRoleSkill"]] = relationship(back_populates="skill")
    job_skills: Mapped[list["JobSkill"]] = relationship(back_populates="skill")
    assessment_questions: Mapped[list["AssessmentQuestion"]] = relationship(back_populates="skill", cascade="all, delete-orphan")
    learning_resources: Mapped[list["LearningResource"]] = relationship(back_populates="skill", cascade="all, delete-orphan")
    student_skills: Mapped[list["StudentSkill"]] = relationship(back_populates="skill")


class CareerRole(Base):
    __tablename__ = "career_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    skills: Mapped[list["CareerRoleSkill"]] = relationship(back_populates="career_role", cascade="all, delete-orphan")


class CareerRoleSkill(Base):
    __tablename__ = "career_role_skills"
    __table_args__ = (UniqueConstraint("career_role_id", "skill_id", name="uq_career_role_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    career_role_id: Mapped[int] = mapped_column(ForeignKey("career_roles.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    required_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    importance_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    career_role: Mapped["CareerRole"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="role_links")


class JobPosting(Base):
    __tablename__ = "job_postings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="manual")
    posted_date: Mapped[str | None] = mapped_column(String(40))
    # Optional fields
    employment_type: Mapped[str | None] = mapped_column(String(60))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    application_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))

    job: Mapped["JobPosting"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="job_skills")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(Text, nullable=False)
    option_b: Mapped[str] = mapped_column(Text, nullable=False)
    option_c: Mapped[str] = mapped_column(Text, nullable=False)
    option_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    topic: Mapped[str | None] = mapped_column(String(100))
    subtopic: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Stable key of questions loaded from app/question_bank (e.g. "python:007"); NULL for staff-authored ones.
    bank_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_assessment_questions_skill_active", "skill_id", "is_active"),)

    skill: Mapped["Skill"] = relationship(back_populates="assessment_questions")
    # No cascade: attempt history keeps its own snapshot even if a question is removed.
    attempts: Mapped[list["AssessmentAttemptQuestion"]] = relationship(back_populates="question", passive_deletes=True)


class AssessmentAttempt(Base):
    """One sitting of an assessment. Created when questions are delivered, scored on submit.

    status: in_progress -> submitted | expired. Only submitted attempts count anywhere.
    Version 1 rows are migrated as submitted (they predate per-question records).
    """

    __tablename__ = "assessment_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", server_default="submitted")
    difficulty: Mapped[str | None] = mapped_column(String(20))  # beginner | intermediate | advanced | mixed
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_level: Mapped[int | None] = mapped_column(Integer)
    answers_json: Mapped[str] = mapped_column(Text, default="{}")
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_attempts_user_status", "user_id", "status"),)

    user: Mapped["User"] = relationship(back_populates="assessment_attempts")
    skill: Mapped["Skill"] = relationship()
    questions: Mapped[list["AssessmentAttemptQuestion"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", order_by="AssessmentAttemptQuestion.position"
    )


class AssessmentAttemptQuestion(Base):
    """A delivered question, snapshotted so later question-bank edits never change history."""

    __tablename__ = "assessment_attempt_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_questions.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    option_a: Mapped[str] = mapped_column(Text, nullable=False, default="")
    option_b: Mapped[str] = mapped_column(Text, nullable=False, default="")
    option_c: Mapped[str] = mapped_column(Text, nullable=False, default="")
    option_d: Mapped[str] = mapped_column(Text, nullable=False, default="")
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    topic: Mapped[str | None] = mapped_column(String(100))
    answer: Mapped[str | None] = mapped_column(String(1))  # NULL = not answered
    is_correct: Mapped[bool | None] = mapped_column(Boolean)  # set on submit

    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="questions")
    question: Mapped["AssessmentQuestion | None"] = relationship(back_populates="attempts")


class StudentSkill(Base):
    __tablename__ = "student_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_student_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(20), default="assessment")  # assessment, self_reported
    # Evidence: when and by which submitted attempt the level was last set.
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_attempts.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="student_skills")
    skill: Mapped["Skill"] = relationship(back_populates="student_skills")


class LearningResource(Base):
    __tablename__ = "learning_resources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), default="Web")
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), default="documentation")
    difficulty: Mapped[str] = mapped_column(String(30), default="beginner")
    description: Mapped[str] = mapped_column(Text, default="")
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    estimated_hours: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["Skill"] = relationship(back_populates="learning_resources")
    progress: Mapped[list["LearningProgress"]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="not_started")
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "resource_id", name="uq_user_resource"),)

    user: Mapped["User"] = relationship(back_populates="learning_progress")
    resource: Mapped["LearningResource"] = relationship(back_populates="progress")


class MentoringNote(Base):
    __tablename__ = "mentoring_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(30), default="general")  # general, feedback, resource_recommendation, concern
    # Optional learning resource recommended by the mentor.
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resources.id", ondelete="SET NULL"))
    # Private notes (e.g. concerns) are visible only to staff.
    visible_to_student: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_mentoring_notes_student_created", "student_id", "created_at"),)

    teacher: Mapped["User"] = relationship(foreign_keys=[teacher_id], back_populates="mentoring_notes")
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    resource: Mapped["LearningResource | None"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Index for common queries
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_refresh_user_expires", "user_id", "expires_at"),)

class PasswordResetToken(Base):
    """Single-use, expiring password-reset token. Only a SHA-256 hash is stored."""

    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeacherInvitation(Base):
    """Administrator-issued invitation; the only way to obtain a teacher account."""

    __tablename__ = "teacher_invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    invited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentSelfSkill(Base):
    """A skill level the student claims. Kept apart from StudentSkill (assessed
    proficiency) so self-reported levels never count as proven proficiency."""

    __tablename__ = "student_self_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_student_self_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    skill: Mapped["Skill"] = relationship()
