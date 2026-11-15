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
