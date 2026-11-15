import { useCallback, useEffect, useState } from 'react';
import { errorMessage, request } from '../api/client';
import type {
  AssessmentSkill,
  Career,
  Dashboard,
  FacultySummary,
  Gap,
  Job,
  JobPage,
  ProgressSummary,
  Resource,
  Role,
  Skill,
  SkillDemand,
} from '../types';

/** Loads the datasets the signed-in user's role may see, and keeps the selected career's gap analysis in sync. */
export function useAppData(role: Role, onError: (message: string) => void) {
  const isStudent = role === 'student';
  const [online, setOnline] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [careers, setCareers] = useState<Career[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [analytics, setAnalytics] = useState<SkillDemand[]>([]);
  const [faculty, setFaculty] = useState<FacultySummary | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assessmentSkills, setAssessmentSkills] = useState<AssessmentSkill[]>([]);
  const [careerId, setCareerId] = useState('');
  const [gap, setGap] = useState<Gap | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, s, d, res, a, j, as] = await Promise.all([
        request<Career[]>('/api/v1/careers'),
        request<Skill[]>('/api/v1/skills'),
        request<Dashboard>('/api/v1/dashboard'),
        request<Resource[]>('/api/v1/resources'),
        request<SkillDemand[]>('/api/v1/analytics/skills'),
        request<JobPage>('/api/v1/jobs?page_size=100'),
        request<AssessmentSkill[]>('/api/v1/assessments/skills'),
      ]);
      setCareers(c);
      setSkills(s);
      setDashboard(d);
      setResources(res);
      setAnalytics(a);
      setJobs(j.items);
      setAssessmentSkills(as);
      setCareerId((old) => old || String(c[0]?.id || ''));
      if (isStudent) setProgress(await request<ProgressSummary>('/api/v1/progress'));
      else setFaculty(await request<FacultySummary>('/api/v1/faculty/summary'));
      setOnline(true);
    } catch (e) {
      setOnline(false);
      onError(errorMessage(e));
    } finally {
      setLoaded(true);
    }
  }, [isStudent, onError]);

  useEffect(() => {
    load();
  }, [load]);

  // Students only: re-fetch the gap analysis when the career changes or after progress reloads.
  useEffect(() => {
    if (isStudent && careerId) {
      request<Gap>('/api/v1/gaps/' + careerId)
        .then(setGap)
        .catch((e) => onError(errorMessage(e)));
    }
  }, [isStudent, careerId, progress, onError]);

  return {
    online,
    loaded,
    careers,
    skills,
    dashboard,
    resources,
    progress,
    analytics,
    faculty,
    jobs,
    assessmentSkills,
    role: careerId,
    setRole: setCareerId,
    gap,
    load,
  };
}

export type AppData = ReturnType<typeof useAppData>;
