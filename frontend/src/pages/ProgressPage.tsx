import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, CheckCircle2, ClipboardList } from 'lucide-react';
import { errorMessage, request } from '../api/client';
import { Empty, Metric } from '../components/common';
import { Alert } from '../components/ui';
import type { HistoryItem, ProgressSummary, Resource } from '../types';

export function ProgressPage({ progress }: { progress: ProgressSummary | null }) {
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState('');
  const [learning, setLearning] = useState<Resource[] | null>(null);
  useEffect(() => {
    request<HistoryItem[]>('/api/v1/assessments/history').then(setHistory).catch((e) => setError(errorMessage(e)));
    request<Resource[]>('/api/v1/learning/history').then(setLearning).catch((e) => setError(errorMessage(e)));
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
      <section className="panel">
        <h2>Learning history</h2>
        {learning?.map((r) => (
          <div className="gaprow" key={r.id}>
            <div>
              <a href={r.url} target="_blank" rel="noreferrer noopener" className="table-link">{r.title}</a>
              <small>
                {r.skill} · {r.provider}
                {r.started_at && ` · started ${new Date(r.started_at).toLocaleDateString()}`}
                {r.completed_at && ` · completed ${new Date(r.completed_at).toLocaleDateString()}`}
                {r.notes && ` · notes: ${r.notes.slice(0, 80)}${r.notes.length > 80 ? '…' : ''}`}
              </small>
            </div>
            <span className="pill">{r.status.replace('_', ' ')}</span>
          </div>
        ))}
        {learning && !learning.length && <Empty text="Start a resource from your learning path to see it here." />}
      </section>
    </>
  );
}
