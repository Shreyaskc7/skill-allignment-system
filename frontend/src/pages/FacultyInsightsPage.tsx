import { Award, Briefcase, ClipboardList, GraduationCap } from 'lucide-react';
import { Metric } from '../components/common';
import type { FacultySummary } from '../types';

export function FacultyInsightsPage({ faculty }: { faculty: FacultySummary | null }) {
  return (
    <>
      <div className="metrics">
        <Metric icon={<GraduationCap />} label="Student profiles" value={faculty?.students ?? 0} />
        <Metric icon={<Briefcase />} label="Job postings" value={faculty?.job_postings ?? 0} />
        <Metric icon={<ClipboardList />} label="Assessments" value={faculty?.assessments ?? 0} />
        <Metric icon={<Award />} label="Average score" value={`${faculty?.average_assessment_score ?? 0}%`} />
      </div>
      <section className="panel">
        <h2>Department snapshot</h2>
        <p className="muted">
          Aggregate local demo environment metrics. This view is not access-controlled and should be secured before
          institutional deployment.
        </p>
        <p>
          Skills catalogued: <b>{faculty?.skills_catalogued ?? 0}</b>
        </p>
      </section>
    </>
  );
}
