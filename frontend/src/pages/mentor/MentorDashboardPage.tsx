import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BookOpen, ClipboardList, Target, Users } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { Empty, Metric } from '../../components/common';
import { Alert, LoadingScreen } from '../../components/ui';
import type { MentorDashboard } from '../../types';

export function MentorDashboardPage() {
  const [d, setD] = useState<MentorDashboard | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    request<MentorDashboard>('/api/v1/mentor/dashboard').then(setD).catch((e) => setError(errorMessage(e)));
  }, []);
  if (error) return <Alert>{error}</Alert>;
  if (!d) return <LoadingScreen />;

  return (
    <>
      <p className="muted">Showing {d.scope}. All figures are calculated from students’ own records.</p>
      <div className="metrics">
        <Metric icon={<Users />} label="Active students" value={d.total_students} />
        <Metric icon={<ClipboardList />} label="Took an assessment"
          value={d.total_students ? `${d.participating} / ${d.total_students}` : '0'} />
        <Metric icon={<Target />} label="Average score" value={d.average_score == null ? '–' : `${d.average_score}%`} />
        <Metric icon={<BookOpen />} label="Average alignment"
          value={d.average_alignment == null ? '–' : `${d.average_alignment}%`} />
      </div>

      <section className="panel">
        <h2>
          <AlertTriangle size={18} className="warn-icon" aria-hidden="true" /> Students needing attention ({d.needs_attention.length})
        </h2>
        <p className="muted">
          Flagged when a student has no assessment in 14 days, an average below 50%, alignment below 40%, no
          target career, or no tracked learning.
        </p>
        {d.needs_attention.map((s) => (
          <div className="gaprow" key={s.id}>
            <div>
              <b>{s.full_name}</b>
              <small>{s.reasons.join(' · ')}</small>
            </div>
            <Link to={`/app/mentor/students/${s.id}`} className="link-button">Review →</Link>
          </div>
        ))}
        {!d.needs_attention.length && (
          <Empty text={d.total_students ? 'No students need attention right now.' : 'No students are assigned to you yet.'} />
        )}
      </section>
      <Link to="/app/mentor/students" className="secondary">View all students</Link>
    </>
  );
}
