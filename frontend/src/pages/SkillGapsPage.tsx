import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, ClipboardList, Info } from 'lucide-react';
import { errorMessage, request } from '../api/client';
import { CareerSelect } from '../components/common';
import { Alert, LoadingScreen } from '../components/ui';
import type { AppData } from '../hooks/useAppData';
import type { GapAnalysis, GapStatus } from '../types';

const STATUS: Record<GapStatus, string> = { critical: 'Critical gap', needs_improvement: 'Needs improvement', meets: 'Meets requirement' };

export function SkillGapsPage({ data }: { data: AppData }) {
  const { careers, role, setRole, progress } = data;
  const [g, setG] = useState<GapAnalysis | null>(null);
  const [error, setError] = useState('');
  const [explain, setExplain] = useState(false);

  useEffect(() => {
    if (!role) return;
    setG(null);
    request<GapAnalysis>(`/api/v1/gaps/${role}`).then(setG).catch((e) => setError(errorMessage(e)));
  }, [role, progress]);

  return (
    <>
      <div className="toolbar">
        <CareerSelect careers={careers} role={role} onChange={setRole} />
        {g && <div className="scorechip">Alignment {g.alignment_score}%</div>}
        <Link to="/app/careers" className="link-button">Compare careers <ArrowRight size={14} /></Link>
      </div>
      {error && <Alert>{error}</Alert>}
      {!g && !error && <LoadingScreen />}
      {g && (
        <>
          <div className="gap-summary">
            <div className="critical"><b>{g.summary.critical}</b><small>Critical gaps</small></div>
            <div className="improve"><b>{g.summary.needs_improvement}</b><small>Need improvement</small></div>
            <div className="meets"><b>{g.summary.meets}</b><small>Meet requirement</small></div>
            <div><b>{g.summary.unassessed}</b><small>Not assessed yet</small></div>
          </div>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>{g.career}</h2>
                <p className="muted">{g.description}</p>
              </div>
              <button className="link-button" onClick={() => setExplain((x) => !x)} aria-expanded={explain}>
                <Info size={14} /> How is this calculated?
              </button>
            </div>
            {explain && (
              <Alert kind="info">
                <code>{g.formula}</code>
                <br />Each skill can add at most its share of the role’s total weight. Levels come only from submitted
                assessments; self-reported levels are shown for reference but never counted. Unassessed skills count as 0.
                This is a rule-based score, not a prediction of being hired.
              </Alert>
            )}
            {g.skills.map((s) => (
              <div className={`gap-row status-${s.status}`} key={s.skill_id}>
                <div className="gap-name">
                  <b>{s.skill}</b>
                  <span className={`pill gap-${s.status}`}>{STATUS[s.status]}</span>
                  <small>
                    {s.assessed
                      ? `Assessed level ${s.current_level}/5${s.last_assessed_at ? ` · ${new Date(s.last_assessed_at).toLocaleDateString()}` : ''}`
                      : 'Not assessed'}
                    {' · '}required {s.required_level}/5 · weight {s.importance}
                    {s.self_reported_level != null && ` · self-reported ${s.self_reported_level}/5 (not counted)`}
                  </small>
                </div>
                <div className="contribution" title={`${s.contribution} of a possible ${s.max_contribution} points`}>
                  <div className="contribution-bar">
                    <i style={{ width: `${s.max_contribution ? (s.contribution / s.max_contribution) * 100 : 0}%` }} />
                  </div>
                  <small>+{s.contribution} / {s.max_contribution} pts</small>
                </div>
                {s.evidence_attempt_id && (
                  <Link to={`/app/assessment/results/${s.evidence_attempt_id}`} className="link-button small">Evidence</Link>
                )}
              </div>
            ))}
          </section>

          <section className="panel">
            <h3>Recommended next steps</h3>
            {g.next_steps.map((n, i) => (
              <div className="gaprow" key={i}>
                <div>
                  <b>{n.type === 'assess' ? <ClipboardList size={14} /> : <BookOpen size={14} />} {n.text}</b>
                </div>
                {n.type === 'assess' && <Link to="/app/assessment" className="link-button">Assess →</Link>}
                {n.resource && <a href={n.resource.url} target="_blank" rel="noreferrer" className="link-button">Open ↗</a>}
              </div>
            ))}
          </section>
        </>
      )}
    </>
  );
}
