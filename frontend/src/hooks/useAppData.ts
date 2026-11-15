import { useCallback, useEffect, useState } from 'react';
import { errorMessage, request } from '../api/client';
import type {
  AssessmentSkill,
  Career,
  Dashboard,
  FacultySummary,
  Gap,
  Job,
  ProgressSummary,
  Resource,
  Skill,
  SkillDemand,
} from '../types';

/** Loads every dataset the screens need and keeps the selected career's gap analysis in sync. */
export function useAppData(setNotice: (message: string) => void) {
  const [online, setOnline] = useState(false);
  const [careers, setCareers] = useState<Career[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [analytics, setAnalytics] = useState<SkillDemand[]>([]);
  const [faculty, setFaculty] = useState<FacultySummary | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assessmentSkills, setAssessmentSkills] = useState<AssessmentSkill[]>([]);
  const [role, setRole] = useState('');
  const [gap, setGap] = useState<Gap | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, s, d, res, p, a, f, j, as] = await Promise.all([
        request<Career[]>('/api/v1/careers'),
        request<Skill[]>('/api/v1/skills'),
        request<Dashboard>('/api/v1/dashboard'),
        request<Resource[]>('/api/v1/resources'),
        request<ProgressSummary>('/api/v1/progress'),
        request<SkillDemand[]>('/api/v1/analytics/skills'),
        request<FacultySummary>('/api/v1/faculty/summary'),
        request<Job[]>('/api/v1/jobs'),
        request<AssessmentSkill[]>('/api/v1/assessments/skills'),
      ]);
      setCareers(c);
      setSkills(s);
      setDashboard(d);
      setResources(res);
      setProgress(p);
      setAnalytics(a);
      setFaculty(f);
      setJobs(j);
      setAssessmentSkills(as);
      setRole((old) => old || String(c[0]?.id || ''));
      setOnline(true);
    } catch (e) {
      setOnline(false);
      setNotice(errorMessage(e) + ' — start FastAPI and check its database connection.');
    }
  }, [setNotice]);

  useEffect(() => {
    load();
  }, [load]);

  // Re-fetch the gap analysis when the role changes or after any reload of progress data.
  useEffect(() => {
    if (role) {
      request<Gap>('/api/v1/gaps/' + role)
        .then(setGap)
        .catch((e) => setNotice(errorMessage(e)));
    }
  }, [role, progress, setNotice]);

  return {
    online,
    careers,
    skills,
    dashboard,
    resources,
    progress,
    analytics,
    faculty,
    jobs,
    assessmentSkills,
    role,
    setRole,
    gap,
    load,
  };
}

export type AppData = ReturnType<typeof useAppData>;
