import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, CheckCircle2, ClipboardList } from 'lucide-react';
import { errorMessage, request } from '../api/client';
import { Empty, Metric } from '../components/common';
import { Alert } from '../components/ui';
import type { HistoryItem, ProgressSummary } from '../types';

export function ProgressPage({ progress }: { progress: ProgressSummary | null }) {
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    request<HistoryItem[]>('/api/v1/assessments/history').then(setHistory).catch((e) => setError(errorMessage(e)));
  }, [progress]);

  return (
    <>
      <div className="metrics">
        <Metric icon={<ClipboardList />} label="Assessments" value={history?.length ?? 0} />
        <Metric icon={<CheckCircle2 />} label="Resources completed" value={progress?.resources?.completed || 0} />
        <Metric icon={<Activity />} label="In progress" value={progress?.resources?.in_progress || 0} />
      </div>
      <section className="panel">
        <h2>Assessment history</h2>
        {error && <Alert>{error}</Alert>}
        {history?.map((a) => (
          <div className="gaprow" key={a.id}>
            <div>
              <Link to={`/app/assessment/results/${a.id}`} className="table-link">{a.skill}</Link>
              <small>
                {new Date(a.created_at).toLocaleString()} · {a.correct}/{a.total} correct
                {a.difficulty && ` · ${a.difficulty}`}{a.estimated_level != null && ` · level ${a.estimated_level}/5`}
              </small>
            </div>
            <span className="scorechip">{a.score_percent}%</span>
          </div>
        ))}
        {history && !history.length && <Empty text="Complete an assessment to start tracking your progress." />}
      </section>
    </>
  );
}
