/** Legacy page names (kept for the header title). */
export type Page =
  | 'Overview'
  | 'Assessment'
  | 'Skill Gaps'
  | 'Learning Resources'
  | 'Job Market'
  | 'Progress'
  | 'Faculty Insights';

export type Career = {
  id: number;
  name: string;
  description: string;
  skills: { skill_id: number; skill_name: string; required_level: number; importance_weight: number }[];
};

export type Skill = { id: number; name: string; category: string; description?: string | null };

export type ProgressStatus = 'not_started' | 'in_progress' | 'completed';

export type Resource = {
  id: number;
  skill_id: number;
  skill: string;
  title: string;
  provider: string;
  url: string;
  type: string;
  difficulty: string;
  description: string;
  is_free: boolean;
  status: ProgressStatus;
};

export type Dashboard = {
  job_count: number;
  skill_count: number;
  assessment_count: number;
  resource_count: number;
  top_skills: { name: string; count: number }[];
};

export type GapItem = {
  skill_id: number;
  skill: string;
  current_level: number;
  required_level: number;
  importance: number;
  gap: number;
  priority: 'High' | 'Medium' | 'On track';
};

export type Gap = { career: string; alignment_score: number; skills: GapItem[] };

export type ProgressSummary = {
  attempts: { skill: string; score: number; date: string | null }[];
  resources: { completed: number; in_progress: number; total_tracked: number };
};

export type SkillDemand = { skill: string; postings: number };

export type FacultySummary = {
  students: number;
  job_postings: number;
  assessments: number;
  skills_catalogued: number;
  average_assessment_score: number;
};

export type Job = {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  source: string;
  skills: string[];
};

export type Difficulty = 'beginner' | 'intermediate' | 'advanced';

export type AssessmentSkill = {
  id: number;
  name: string;
  category: string;
  question_count: number;
  by_difficulty: Record<Difficulty, number>;
};

export type DeliveredQuestion = {
  id: number;
  position: number;
  question: string;
  difficulty: Difficulty;
  options: Record<'A' | 'B' | 'C' | 'D', string>;
};

export type AttemptDelivery = {
  attempt_id: number;
  skill_id: number;
  skill: string;
  status: 'in_progress';
  difficulty: string;
  resumed: boolean;
  started_at: string;
  expires_at: string | null;
  server_time: string;
  questions: DeliveredQuestion[];
};

export type Breakdown = { name: string; correct: number; total: number; percent: number };

export type AttemptResult = {
  attempt_id: number;
  skill_id: number;
  skill: string;
  status: 'submitted';
  difficulty: string | null;
  total: number;
  correct: number;
  unanswered: number;
  score_percent: number;
  estimated_level: number | null;
  level_bands: string;
  time_spent_seconds: number | null;
  submitted_at: string;
  by_difficulty: Breakdown[];
  by_topic: Breakdown[];
  review: {
    question_id: number | null;
    position: number;
    question: string;
    options: Record<'A' | 'B' | 'C' | 'D', string>;
    your_answer: string | null;
    correct_option: string;
    is_correct: boolean;
    explanation: string;
    difficulty: Difficulty;
    topic: string | null;
  }[];
  detail_available: boolean;
};

export type HistoryItem = {
  id: number;
  skill: string;
  score_percent: number;
  correct: number;
  total: number;
  estimated_level: number | null;
  difficulty: string | null;
  created_at: string;
};

export type BankQuestion = {
  id: number;
  skill_id: number;
  skill: string;
  question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: 'A' | 'B' | 'C' | 'D';
  explanation: string;
  difficulty: Difficulty;
  topic: string | null;
  subtopic: string | null;
  is_active: boolean;
  source: 'bundled' | 'staff';
};

export type ImportResult = { imported: number; skipped: number; skills_found: Record<string, number>; message: string };

export type Role = 'student' | 'teacher' | 'admin';

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type Invitation = {
  id: number;
  email: string;
  full_name: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  invite_url?: string;
};

export type ExperienceLevel = 'fresher' | 'internship' | '0-1 years' | '1-3 years' | '3+ years';

export type StudentProfile = {
  user_id: number;
  email: string;
  full_name: string;
  phone: string | null;
  date_of_birth: string | null;
  location: string | null;
  college: string | null;
  degree: string | null;
  department: string | null;
  specialization: string | null;
  current_semester: number | null;
  graduation_year: number | null;
  cgpa: number | null;
  career_interests: string | null;
  target_job_roles: string | null;
  technical_skills: string | null;
  soft_skills: string | null;
  preferred_locations: string | null;
  experience_level: ExperienceLevel | null;
  target_career_id: number | null;
  target_career_name: string | null;
  has_profile_image: boolean;
  has_resume: boolean;
  completion: { percent: number; missing: string[] };
};

export type SelfSkill = { skill_id: number; skill_name: string; category: string; level: number };

export type StudentDashboard = {
  user: { full_name: string; email: string };
  profile_completion: { percent: number; missing: string[] };
  target_career: null | {
    id: number;
    name: string;
    alignment_score: number;
    skills_met: number;
    skills_total: number;
    missing_skills: {
      skill_id: number;
      skill: string;
      current_level: number;
      required_level: number;
      importance: number;
      priority: 'High' | 'Medium' | 'On track';
      assessed: boolean;
    }[];
  };
  assessed_skills: { skill_id: number; skill: string; level: number; updated_at: string }[];
  self_reported_skill_count: number;
  assessments: {
    count: number;
    average_score: number | null;
    best_score: number | null;
    latest: { skill: string; score_percent: number; created_at: string }[];
  };
  learning: { completed: number; in_progress: number; tracked: number };
  recommended_resources: {
    id: number;
    title: string;
    skill: string;
    provider: string;
    url: string;
    type: string;
    status: ProgressStatus;
  }[];
  matching_jobs: { available: boolean; reason: string };
  recent_activity: { type: 'assessment' | 'learning'; text: string; at: string }[];
};

export type StudentSummary = {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  college: string | null;
  department: string | null;
  current_semester: number | null;
  target_career: null | { id: number; name: string; alignment_score: number; high_priority_gaps: string[] };
  assessments: { count: number; average_score: number | null; last_at: string | null };
  learning: { completed: number; in_progress: number };
  needs_attention: string[];
};

export type MentorDashboard = {
  scope: string;
  total_students: number;
  participating: number;
  average_score: number | null;
  average_alignment: number | null;
  resources_completed: number;
  needs_attention: { id: number; full_name: string; reasons: string[] }[];
};

export type NoteType = 'general' | 'feedback' | 'resource_recommendation' | 'concern';

export type MentoringNote = {
  id: number;
  teacher_id: number;
  teacher_name: string;
  note: string;
  note_type: NoteType;
  visible_to_student: boolean;
  created_at: string;
  resource: null | { id: number; title: string; url: string };
};

export type StudentDetail = {
  summary: StudentSummary;
  profile: null | Record<string, string | number | null>;
  assessments: { id: number; skill: string; score_percent: number; correct: number; total: number; created_at: string }[];
  skill_performance: { skill: string; attempts: number; best: number; latest: number; average: number }[];
  gaps: null | { career: string; alignment_score: number; skills: GapItem[] };
  learning: { resource: string; skill: string; status: ProgressStatus; updated_at: string }[];
  self_reported_skills: { skill: string; level: number }[];
  notes: MentoringNote[];
};

export type Assignment = {
  id: number;
  student_id: number;
  student_name: string;
  student_email: string;
  teacher_id: number;
  teacher_name: string;
  assigned_by: string | null;
  assigned_at: string;
  is_active: boolean;
  removed_at: string | null;
  removal_reason: string | null;
};

export type AdminUser = { id: number; full_name: string; email: string; role: Role; is_active: boolean };

export type TeacherProfile = {
  user_id: number;
  email: string;
  full_name: string;
  phone: string | null;
  qualification: string | null;
  institution: string | null;
  department: string | null;
  designation: string | null;
  specialization: string | null;
  years_experience: number | null;
  areas_of_expertise: string | null;
  biography: string | null;
  has_profile_image: boolean;
};
