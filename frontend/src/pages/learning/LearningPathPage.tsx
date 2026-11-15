import { useCallback, useEffect, useState } from 'react';
import { safeUrl } from '../../api/safeUrl';
import { Link } from 'react-router-dom';
import { CheckCircle2, ClipboardList, ExternalLink, Info, PlayCircle, RefreshCw } from 'lucide-react';
import { ApiError, errorMessage, postJson, request } from '../../api/client';
import { useApp } from '../../components/AppLayout';
import { Alert, LoadingScreen, useToast } from '../../components/ui';
import type { LearningPath, PathStep, ProgressStatus, Resource } from '../../types';

const STEP_LABEL: Record<PathStep['status'], string> = {
  not_assessed: 'Assess first', todo: 'To do', in_progress: 'In progress', ready_to_reassess: 'Ready to reassess',
};

export function ResourceActions({ r, onChange }: { r: Resource; onChange: (status: ProgressStatus) => void }) {
  return (
    <div className="resource-actions">
      <a href={safeUrl(r.url)} target="_blank" rel="noreferrer noopener" className="link-button">Open <ExternalLink size={12} /></a>
      {r.status === 'not_started' && <button className="link-button" onClick={() => onChange('in_progress')}><PlayCircle size={13} /> Start</button>}
      {r.status !== 'completed' && <button className="link-button" onClick={() => onChange('completed')}><CheckCircle2 size={13} /> Mark completed</button>}
      {r.status === 'completed' && <span className="pill">completed</span>}
    </div>
  );
}

export function LearningPathPage() {
  const { data } = useApp();
  const toast = useToast();
  const [path, setPath] = useState<LearningPath | null>(null);
  const [error, setError] = useState('');
  const [needsTarget, setNeedsTarget] = useState(false);
  const [showRules, setShowRules] = useState(false);

  const load = useCallback(() => {
    request<LearningPath>('/api/v1/learning/path')
      .then((p) => { setPath(p); setNeedsTarget(false); })
      .catch((e) => (e instanceof ApiError && e.status === 409 ? setNeedsTarget(true) : setError(errorMessage(e))));
  }, []);
  useEffect(load, [load]);

  async function setStatus(r: Resource, status: ProgressStatus) {
    try {
      await postJson(`/api/v1/progress/${r.id}`, { status });
      toast('success', status === 'completed' ? `Completed “${r.title}”.` : `Started “${r.title}”.`);
      load();
      data.load();
    } catch (e) {
      toast('error', errorMessage(e));
    }
  }

  if (needsTarget) {
    return <Alert kind="info">Choose a target career first on the <Link to="/app">Dashboard</Link> or <Link to="/app/careers">Careers</Link> page; your learning path is built from its skill gaps.</Alert>;
  }
  if (error) return <Alert>{error}</Alert>;
  if (!path) return <LoadingScreen />;

  return (
    <>
      <section className="panel path-head">
        <div>
          <h2>Learning path: {path.career}</h2>
          <p className="muted">
            {path.totals.steps} skill(s) to develop · {path.totals.skills_met} already met · {path.totals.resources_completed} resource(s)
            completed on this path · alignment {path.alignment_score}%
          </p>
        </div>
        <button className="link-button" onClick={() => setShowRules((x) => !x)} aria-expanded={showRules}><Info size={14} /> How is this path built?</button>
      </section>
      {showRules && <Alert kind="info"><span className="pre">{path.rules}</span></Alert>}

      {!path.steps.length && <Alert kind="success">You meet every requirement for {path.career}. Keep practising and reassess regularly.</Alert>}

      <ol className="path">
        {path.steps.map((s) => (
          <li key={s.skill_id} className={`path-step step-${s.status}`}>
            <div className="step-marker" aria-hidden="true">{s.step}</div>
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h3>{s.skill} <span className={`pill gap-${s.gap_status}`}>{s.gap_status.replace('_', ' ')}</span></h3>
                  <small className="muted">
                    {s.assessed ? `Level ${s.current_level}/5` : 'Not assessed'} → required {s.required_level}/5 · weight {s.importance} ·
                    {' '}{s.target_difficulty} resources
                  </small>
                </div>
                <span className={`step-status ${s.status}`}>{STEP_LABEL[s.status]}</span>
              </div>
              <p className="step-action">{s.action}</p>
              {(s.status === 'not_assessed' || s.status === 'ready_to_reassess') && (
                <Link to="/app/assessment" className="secondary small-btn">
                  {s.status === 'not_assessed' ? <ClipboardList size={14} /> : <RefreshCw size={14} />} {s.status === 'not_assessed' ? 'Take assessment' : 'Reassess'}
                </Link>
              )}
              <div className="step-resources">
                {s.resources.map((r) => (
                  <article key={r.id} className={`step-resource status-${r.status}`}>
                    <div>
                      <b>{r.title}</b>
                      <small>{r.provider} · {r.type} · {r.difficulty}{r.status === 'in_progress' ? ' · in progress' : ''}</small>
                    </div>
                    <ResourceActions r={r} onChange={(st) => setStatus(r, st)} />
                  </article>
                ))}
                {!s.resources.length && s.status !== 'ready_to_reassess' && (
                  <p className="muted small">No resources in the catalogue for this skill yet.</p>
                )}
              </div>
              {s.completed_resources > 0 && <small className="muted">{s.completed_resources} resource(s) completed for this skill.</small>}
            </section>
          </li>
        ))}
      </ol>

      {path.completed_skills.length > 0 && (
        <section className="panel">
          <h3>Already met</h3>
          <div className="tags">{path.completed_skills.map((c) => <span key={c.skill_id} className="has">{c.skill} ({c.current_level}/{c.required_level})</span>)}</div>
        </section>
      )}
    </>
  );
}
