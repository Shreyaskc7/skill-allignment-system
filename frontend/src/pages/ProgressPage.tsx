import { Activity, CheckCircle2, ClipboardList } from 'lucide-react';
import { Empty, Metric } from '../components/common';
import type { ProgressSummary } from '../types';

export function ProgressPage({ progress }: { progress: ProgressSummary | null }) {
  const attempts = progress?.attempts || [];
  return (
    <>
      <div className="metrics">
        <Metric icon={<ClipboardList />} label="Assessments" value={attempts.length} />
        <Metric icon={<CheckCircle2 />} label="Resources completed" value={progress?.resources?.completed || 0} />
        <Metric icon={<Activity />} label="In progress" value={progress?.resources?.in_progress || 0} />
      </div>
      <section className="panel">
        <h2>Assessment history</h2>
        {attempts.map((a, i) => (
          <div className="gaprow" key={i}>
            <div>
              <b>{a.skill}</b>
              <small>{a.date ? new Date(a.date).toLocaleString() : ''}</small>
            </div>
            <span className="scorechip">{a.score}%</span>
          </div>
        ))}
        {!attempts.length && <Empty text="Complete an assessment to start tracking your progress." />}
      </section>
    </>
  );
}
