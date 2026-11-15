import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2, XCircle } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { Metric } from '../../components/common';
import { Alert, LoadingScreen } from '../../components/ui';
import type { AttemptResult, Breakdown } from '../../types';

function Bars({ title, items }: { title: string; items: Breakdown[] }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {items.map((b) => (
        <div className="barrow wide" key={b.name}>
          <span>{b.name}</span>
          <div className="bar"><i style={{ width: `${Math.max(2, b.percent)}%` }} /></div>
          <b>{b.correct}/{b.total}</b>
        </div>
      ))}
    </section>
  );
}

export function ResultsPage() {
  const { id } = useParams();
  const [r, setR] = useState<AttemptResult | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'wrong'>('all');

  useEffect(() => {
    request<AttemptResult>(`/api/v1/assessments/attempts/${id}`).then(setR).catch((e) => setError(errorMessage(e)));
  }, [id]);
  if (error) return <Alert>{error}</Alert>;
  if (!r) return <LoadingScreen />;
  const shown = r.review.filter((x) => filter === 'all' || !x.is_correct);

  return (
    <>
      <section className="panel result-hero">
        <div>
          <small className="muted">{r.skill} · {new Date(r.submitted_at).toLocaleString()}</small>
          <h2>{r.score_percent}%</h2>
          <p>
            {r.correct} of {r.total} correct{r.unanswered > 0 && ` · ${r.unanswered} unanswered`}
            {r.time_spent_seconds != null && ` · ${Math.round(r.time_spent_seconds / 60)} min`}
          </p>
        </div>
        <div className="level-badge">
          <small>Proficiency level</small>
          <strong>{r.estimated_level ?? '–'}<span>/5</span></strong>
          <small className="muted">{r.level_bands}</small>
        </div>
      </section>

      {!r.detail_available && <Alert kind="info">This attempt was taken before per-question records were kept, so no review is available.</Alert>}

      {r.detail_available && (
        <>
          <div className="metrics">
            <Metric icon={<CheckCircle2 />} label="Correct" value={r.correct} />
            <Metric icon={<XCircle />} label="Incorrect" value={r.total - r.correct - r.unanswered} />
            <Metric icon={<XCircle />} label="Unanswered" value={r.unanswered} />
            <Metric icon={<CheckCircle2 />} label="Difficulty" value={r.difficulty ?? '–'} />
          </div>
          <div className="grid2">
            <Bars title="Performance by difficulty" items={r.by_difficulty} />
            <Bars title="Performance by topic" items={r.by_topic} />
          </div>
          <section className="panel">
            <div className="panel-head">
              <h3>Review answers</h3>
              <div className="segmented" role="group" aria-label="Filter review">
                <button className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>All ({r.review.length})</button>
                <button className={filter === 'wrong' ? 'on' : ''} onClick={() => setFilter('wrong')}>
                  To review ({r.review.filter((x) => !x.is_correct).length})
                </button>
              </div>
            </div>
            {shown.map((x) => (
              <div className={'review-item ' + (x.is_correct ? 'right' : 'wrong')} key={x.position}>
                <div className="review-q">
                  {x.is_correct ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
                  <b className="q-text">{x.position}. {x.question}</b>
                </div>
                <ul className="review-opts">
                  {(Object.entries(x.options) as [string, string][]).map(([k, v]) => (
                    <li key={k} className={(k === x.correct_option ? 'correct ' : '') + (k === x.your_answer && !x.is_correct ? 'chosen' : '')}>
                      <b>{k}</b> <span className="q-text">{v}</span>
                      {k === x.correct_option && <em> correct answer</em>}
                      {k === x.your_answer && !x.is_correct && <em> your answer</em>}
                    </li>
                  ))}
                </ul>
                {!x.your_answer && <small className="muted">Not answered.</small>}
                <p className="explanation">{x.explanation}</p>
                <small className="muted">{x.difficulty}{x.topic && ` · ${x.topic}`}</small>
              </div>
            ))}
          </section>
        </>
      )}
      <div className="runner-nav">
        <Link to="/app/progress" className="secondary">Assessment history</Link>
        <Link to="/app/assessment" className="primary">Take another assessment</Link>
      </div>
    </>
  );
}
