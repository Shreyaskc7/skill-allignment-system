"""Pydantic schemas for request/response validation and API documentation."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


# =====================================================================
# Base schemas
# =====================================================================

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Authentication
# =====================================================================

def _strong_password(v: str) -> str:
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one letter and one number")
    if v.strip() != v:
        raise ValueError("Password must not start or end with spaces")
    return v


def _normalise_email(v: str) -> str:
    return v.strip().lower()


class _PasswordConfirmation(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    _strong = field_validator("password")(classmethod(lambda cls, v: _strong_password(v)))

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class RegisterRequest(_PasswordConfirmation):
    """Public self-registration. Only the student role can be self-registered."""

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    phone: Optional[str] = Field(None, max_length=30, pattern=r"^[0-9+()\-\s]{6,30}$")
    role: Literal["student"] = "student"
    terms_accepted: bool

    _email = field_validator("email")(classmethod(lambda cls, v: _normalise_email(v)))

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Full name is too short")
        return v

    @field_validator("terms_accepted")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and privacy policy")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(classmethod(lambda cls, v: _normalise_email(v)))


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    _email = field_validator("email")(classmethod(lambda cls, v: _normalise_email(v)))


class ResetPasswordRequest(_PasswordConfirmation):
    token: str = Field(min_length=20, max_length=200)


class AcceptInvitationRequest(_PasswordConfirmation):
    token: str = Field(min_length=20, max_length=200)
    full_name: Optional[str] = Field(None, min_length=2, max_length=160)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str

    _strong = field_validator("new_password")(classmethod(lambda cls, v: _strong_password(v)))

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class InvitationCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)

    _email = field_validator("email")(classmethod(lambda cls, v: _normalise_email(v)))


class InvitationOut(BaseSchema):
    id: int
    email: str
    full_name: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    status: str


class InvitationCreated(InvitationOut):
    invite_url: str


class InvitationPreview(BaseModel):
    email: str
    full_name: str


class MessageOut(BaseModel):
    message: str


# =====================================================================
# User
# =====================================================================

class UserOut(BaseSchema):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    @field_validator("role", mode="before")
    @classmethod
    def role_value(cls, v):
        return getattr(v, "value", v)


class AccessTokenResponse(BaseModel):
    """The refresh token is never in the body: it is set as an HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=160)
    email: Optional[EmailStr] = None


# =====================================================================
# Student Profile
# =====================================================================

class StudentProfileBase(BaseModel):
    phone: Optional[str] = Field(None, max_length=30)
    date_of_birth: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=160)
    profile_image_url: Optional[str] = Field(None, max_length=500)

    college: Optional[str] = Field(None, max_length=200)
    degree: Optional[str] = Field(None, max_length=120)
    department: Optional[str] = Field(None, max_length=120)
    specialization: Optional[str] = Field(None, max_length=120)
    current_semester: Optional[int] = Field(None, ge=1, le=12)
    graduation_year: Optional[int] = Field(None, ge=2020, le=2050)
    cgpa: Optional[float] = Field(None, ge=0, le=10)

    career_interests: Optional[str] = None
    target_job_roles: Optional[str] = None
    technical_skills: Optional[str] = None
    soft_skills: Optional[str] = None
    preferred_locations: Optional[str] = None
    experience_level: Optional[str] = Field(None, max_length=60)
    resume_url: Optional[str] = Field(None, max_length=500)


class StudentProfileCreate(StudentProfileBase):
    pass


class StudentProfileUpdate(StudentProfileBase):
    pass


class StudentProfileOut(BaseSchema):
    id: int
    user_id: int
    phone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    location: Optional[str] = None
    profile_image_url: Optional[str] = None
    college: Optional[str] = None
    degree: Optional[str] = None
    department: Optional[str] = None
    specialization: Optional[str] = None
    current_semester: Optional[int] = None
    graduation_year: Optional[int] = None
    cgpa: Optional[float] = None
    career_interests: Optional[str] = None
    target_job_roles: Optional[str] = None
    technical_skills: Optional[str] = None
    soft_skills: Optional[str] = None
    preferred_locations: Optional[str] = None
    experience_level: Optional[str] = None
    resume_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =====================================================================
# Teacher Profile
# =====================================================================

class TeacherProfileBase(BaseModel):
    phone: Optional[str] = Field(None, max_length=30)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    qualification: Optional[str] = Field(None, max_length=200)
    institution: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=120)
    designation: Optional[str] = Field(None, max_length=120)
    specialization: Optional[str] = Field(None, max_length=160)
    years_experience: Optional[int] = Field(None, ge=0, le=60)
    areas_of_expertise: Optional[str] = None
    biography: Optional[str] = None


class TeacherProfileCreate(TeacherProfileBase):
    pass


class TeacherProfileUpdate(TeacherProfileBase):
    pass


class TeacherProfileOut(BaseSchema):
    id: int
    user_id: int
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    qualification: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    specialization: Optional[str] = None
    years_experience: Optional[int] = None
    areas_of_expertise: Optional[str] = None
    biography: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =====================================================================
# Skills
# =====================================================================

class SkillBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=60, default="technical")
    description: Optional[str] = None
    esco_identifier: Optional[str] = Field(None, max_length=50)
    esco_label: Optional[str] = Field(None, max_length=200)


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=60)
    description: Optional[str] = None
    esco_identifier: Optional[str] = Field(None, max_length=50)
    esco_label: Optional[str] = Field(None, max_length=200)


class SkillOut(BaseSchema):
    id: int
    name: str
    category: str
    description: Optional[str] = None
    esco_identifier: Optional[str] = None
    esco_label: Optional[str] = None


# =====================================================================
# Career Roles
# =====================================================================

class CareerRoleSkillBase(BaseModel):
    skill_id: int
    required_level: int = Field(ge=1, le=5)
    importance_weight: int = Field(ge=1, le=5)


class CareerRoleSkillCreate(CareerRoleSkillBase):
    pass


class CareerRoleSkillOut(BaseSchema):
    id: int
    career_role_id: int
    skill_id: int
    skill_name: Optional[str] = None
    required_level: int
    importance_weight: int


class CareerRoleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    is_active: bool = True


class CareerRoleCreate(CareerRoleBase):
    skills: List[CareerRoleSkillCreate] = []


class CareerRoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    skills: Optional[List[CareerRoleSkillCreate]] = None


class CareerRoleOut(BaseSchema):
    id: int
    name: str
    description: str
    is_active: bool
    skills: List[CareerRoleSkillOut] = []


# =====================================================================
# Job Postings
# =====================================================================

class JobPostingBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=160)
    description: str = Field(min_length=1)
    employment_type: Optional[str] = Field(None, max_length=60)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    application_url: Optional[str] = Field(None, max_length=500)
    posted_date: Optional[str] = Field(None, max_length=40)


class JobPostingCreate(JobPostingBase):
    source: str = "manual"


class JobPostingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None
    employment_type: Optional[str] = Field(None, max_length=60)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    application_url: Optional[str] = Field(None, max_length=500)
    posted_date: Optional[str] = Field(None, max_length=40)


class JobSkillOut(BaseSchema):
    skill_id: int
    skill_name: str


class JobPostingOut(BaseSchema):
    id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: str
    source: str
    employment_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    application_url: Optional[str] = None
    posted_date: Optional[str] = None
    created_at: datetime
    skills: List[JobSkillOut] = []


class JobImportResult(BaseModel):
    imported: int
    skipped: int
    skills_found: Dict[str, int]
    message: str


# =====================================================================
# Assessment
# =====================================================================

class AssessmentQuestionBase(BaseModel):
    question: str = Field(min_length=1)
    option_a: str = Field(min_length=1)
    option_b: str = Field(min_length=1)
    option_c: str = Field(min_length=1)
    option_d: str = Field(min_length=1)
    correct_option: str = Field(pattern="^[ABCD]$")
    explanation: str = ""
    difficulty: str = Field(pattern="^(beginner|intermediate|advanced)$", default="beginner")
    topic: Optional[str] = Field(None, max_length=100)
    subtopic: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class AssessmentQuestionCreate(AssessmentQuestionBase):
    skill_id: int


class AssessmentQuestionUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=1)
    option_a: Optional[str] = Field(None, min_length=1)
    option_b: Optional[str] = Field(None, min_length=1)
    option_c: Optional[str] = Field(None, min_length=1)
    option_d: Optional[str] = Field(None, min_length=1)
    correct_option: Optional[str] = Field(None, pattern="^[ABCD]$")
    explanation: Optional[str] = None
    difficulty: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    topic: Optional[str] = Field(None, max_length=100)
    subtopic: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class AssessmentQuestionOut(BaseSchema):
    id: int
    skill_id: int
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: str
    difficulty: str
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    is_active: bool
    created_at: datetime


class AssessmentQuestionPublic(BaseModel):
    """Question without correct answer for delivery to student."""
    id: int
    question: str
    options: Dict[str, str]
    difficulty: str


class AssessmentStartRequest(BaseModel):
    skill_id: int
    question_count: int = Field(default=10, ge=5, le=30)
    difficulty: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced|mixed)$")


class AssessmentQuestionDelivery(BaseModel):
    id: int
    question: str
    options: Dict[str, str]
    difficulty: str


class AssessmentSubmitRequest(BaseModel):
    skill_id: int
    question_ids: List[int]
    answers: Dict[int, str]  # question_id -> A/B/C/D
    time_spent_seconds: Optional[int] = None


class AssessmentAttemptQuestionOut(BaseSchema):
    question_id: int
    question: str
    options: Dict[str, str]
    correct_option: str
    your_answer: str
    is_correct: bool
    explanation: str
    difficulty: str


class AssessmentSubmitResponse(BaseSchema):
    attempt_id: int
    skill_id: int
    skill_name: str
    total_questions: int
    correct_answers: int
    score_percent: float
    estimated_level: int
    questions: List[AssessmentAttemptQuestionOut]


class AssessmentAttemptOut(BaseSchema):
    id: int
    skill_id: int
    skill_name: str
    total_questions: int
    correct_answers: int
    score_percent: float
    time_spent_seconds: Optional[int] = None
    created_at: datetime


# =====================================================================
# Skill Gap Analysis
# =====================================================================

class SkillGapItem(BaseModel):
    skill_id: int
    skill: str
    current_level: int
    required_level: int
    importance: int
    gap: int
    priority: str
    is_assessed: bool


class SkillGapResponse(BaseModel):
    career_id: int
    career: str
    alignment_score: int
    skills: List[SkillGapItem]


# =====================================================================
# Student Skills
# =====================================================================

class StudentSkillOut(BaseSchema):
    skill_id: int
    skill_name: str
    category: str
    level: int
    source: str
    updated_at: datetime


# =====================================================================
# Learning Resources
# =====================================================================

class LearningResourceBase(BaseModel):
    skill_id: int
    title: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="Web", max_length=100)
    url: str = Field(min_length=1, max_length=500)
    resource_type: str = Field(default="documentation", max_length=40)
    difficulty: str = Field(default="beginner", max_length=30)
    description: str = ""
    is_free: bool = True
    estimated_hours: Optional[int] = Field(None, ge=0)


class LearningResourceCreate(LearningResourceBase):
    pass


class LearningResourceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    provider: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    resource_type: Optional[str] = Field(None, max_length=40)
    difficulty: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = None
    is_free: Optional[bool] = None
    estimated_hours: Optional[int] = Field(None, ge=0)


class LearningResourceOut(BaseSchema):
    id: int
    skill_id: int
    skill_name: str
    title: str
    provider: str
    url: str
    resource_type: str
    difficulty: str
    description: str
    is_free: bool
    estimated_hours: Optional[int] = None
    created_at: datetime


# =====================================================================
# Learning Progress
# =====================================================================

class LearningProgressUpdate(BaseModel):
    status: str = Field(pattern="^(not_started|in_progress|completed)$")
    notes: Optional[str] = None


class LearningProgressOut(BaseSchema):
    id: int
    user_id: int
    resource_id: int
    resource_title: str
    skill_name: str
    status: str
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime


# =====================================================================
# Mentoring
# =====================================================================

class MentoringNoteBase(BaseModel):
    student_id: int
    note: str = Field(min_length=1)
    note_type: str = Field(pattern="^(general|feedback|resource_recommendation|concern)$", default="general")


class MentoringNoteCreate(MentoringNoteBase):
    pass


class MentoringNoteUpdate(BaseModel):
    note: Optional[str] = Field(None, min_length=1)
    note_type: Optional[str] = Field(None, pattern="^(general|feedback|resource_recommendation|concern)$")


class MentoringNoteOut(BaseSchema):
    id: int
    teacher_id: int
    teacher_name: str
    student_id: int
    student_name: str
    note: str
    note_type: str
    created_at: datetime


# =====================================================================
# Student-Teacher Assignment
# =====================================================================

class AssignmentCreate(BaseModel):
    student_id: int
    teacher_id: int


class AssignmentOut(BaseSchema):
    id: int
    student_id: int
    student_name: str
    student_email: str
    teacher_id: int
    teacher_name: str
    assigned_by: Optional[int] = None
    assigned_at: datetime
    is_active: bool
    removed_at: Optional[datetime] = None
    removal_reason: Optional[str] = None


# =====================================================================
# Dashboard / Analytics
# =====================================================================

class DashboardOut(BaseModel):
    job_count: int
    skill_count: int
    assessment_count: int
    resource_count: int
    top_skills: List[Dict[str, Any]]


class FacultySummaryOut(BaseModel):
    students: int
    job_postings: int
    assessments: int
    skills_catalogued: int
    average_assessment_score: float


class SkillAnalyticsOut(BaseModel):
    skill: str
    postings: int


# =====================================================================
# Learning Path
# =====================================================================

class LearningPathStep(BaseModel):
    step: int
    skill_id: int
    skill_name: str
    resources: List[LearningResourceOut]


class LearningPathOut(BaseModel):
    career_id: int
    career_name: str
    steps: List[LearningPathStep]


# =====================================================================
# Job Matching
# =====================================================================

class JobMatchOut(BaseModel):
    job: JobPostingOut
    match_percent: int
    matching_skills: List[str]
    missing_skills: List[str]
    additional_skills: List[str]


# =====================================================================
# Audit Log
# =====================================================================

class AuditLogOut(BaseSchema):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


# =====================================================================
# Pagination
# =====================================================================

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int