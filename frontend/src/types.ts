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

export type AssessmentSkill = { id: number; name: string; question_count: number };

export type Question = {
  id: number;
  question: string;
  options: Record<string, string>;
  difficulty: string;
};

export type AssessmentResult = {
  attempt_id: number;
  correct: number;
  total: number;
  score_percent: number;
  estimated_level: number;
  review: {
    question_id: number;
    correct_option: string;
    your_answer: string | null;
    is_correct: boolean;
    explanation: string;
  }[];
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
