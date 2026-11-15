import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Star, Target } from 'lucide-react';
import { errorMessage, putJson, request } from '../api/client';
import { useApp } from '../components/AppLayout';
import { Alert, LoadingScreen, useToast } from '../components/ui';
import type { CareerRecommendation } from '../types';

type Rec = { method: string; assessed_skill_count: number; recommendations: CareerRecommendation[] };

export function CareersPage() {
  const { data } = useApp();
  const toast = useToast();
  const [rec, setRec] = useState<Rec | null>(null);
  const [error, setError] = useState('');
  const [compare, setCompare] = useState<number[]>([]);

  const load = useCallback(() => {
    request<Rec>('/api/v1/careers/recommendations').then(setRec).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load, data.progress]);

  async function setTarget(r: CareerRecommendation) {
    try {
      await putJson('/api/v1/students/me/target-career', { target_career_id: r.career_id });
      data.setRole(String(r.career_id));
      toast('success', `${r.career} is now your target career.`);
      load();
    } catch (e) {
      toast('error', errorMessage(e));
    }
  }

  function toggleCompare(id: number) {
    setCompare((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= 3 ? c : [...c, id]));
  }

  if (error) return <Alert>{error}</Alert>;
  if (!rec) return <LoadingScreen />;
  const compared = rec.recommendations.filter((r) => compare.includes(r.career_id));
  const allSkills = [...new Set(compared.flatMap((r) => r.required_skills.map((s) => s.skill)))].sort();

  return (
    <>
      <p className="muted">{rec.method}</p>
      {rec.assessed_skill_count === 0 && (
        <Alert kind="info">
          You have not taken any assessments yet, so every role starts at 0%. <Link to="/app/assessment">Take an assessment</Link> to
          see meaningful matches.
        </Alert>
      )}

      <div className="career-grid">
        {rec.recommendations.map((r) => (
          <article className={'panel career-card' + (r.is_target ? ' target' : '')} key={r.career_id}>
            <div className="career-top">
              <span className="rank">#{r.rank}</span>
              {r.is_target && <span className="pill"><Target size={11} /> Your target</span>}
            </div>
            <h3>{r.career}</h3>
            <div className="match">
              <strong>{r.alignment_score}%</strong>
              <div className="progress"><i style={{ width: `${r.alignment_score}%` }} /></div>
            </div>
            {r.reasons.map((x) => <p className="reason" key={x}>{x}</p>)}
            <dl className="skill-lists">
              <dt>Matching</dt><dd>{r.matching_skills.join(', ') || '—'}</dd>
              <dt>To improve</dt><dd>{r.skills_to_improve.join(', ') || '—'}</dd>
              <dt>Not assessed</dt><dd>{r.missing_skills.join(', ') || '—'}</dd>
            </dl>
            <div className="career-actions">
              {!r.is_target && <button className="secondary" onClick={() => setTarget(r)}><Star size={14} /> Set as target</button>}
              <Link to="/app/skill-gaps" onClick={() => data.setRole(String(r.career_id))} className="link-button">Gap details →</Link>
              <label className="checkbox inline">
                <input type="checkbox" checked={compare.includes(r.career_id)} onChange={() => toggleCompare(r.career_id)}
                  disabled={!compare.includes(r.career_id) && compare.length >= 3} />
                <span>Compare</span>
              </label>
            </div>
          </article>
        ))}
      </div>

      <section className="panel">
        <h2>Compare careers</h2>
        {compared.length < 2 ? (
          <p className="muted">Tick “Compare” on two or three careers to see their requirements side by side.</p>
        ) : (
          <div className="table-wrap">
            <table className="compare">
              <thead>
                <tr><th>Skill (your level)</th>{compared.map((r) => <th key={r.career_id}>{r.career}<small className="cell-sub">{r.alignment_score}% aligned</small></th>)}</tr>
              </thead>
              <tbody>
                {allSkills.map((skill) => {
                  const mine = compared.flatMap((r) => r.required_skills).find((s) => s.skill === skill)?.current_level ?? 0;
                  return (
                    <tr key={skill}>
                      <td>{skill} <small className="muted">({mine || 'not assessed'})</small></td>
                      {compared.map((r) => {
                        const req = r.required_skills.find((s) => s.skill === skill);
                        return (
                          <td key={r.career_id} className={req ? (mine >= req.required_level ? 'ok' : 'short') : ''}>
                            {req ? `needs ${req.required_level} · w${req.weight}` : '—'}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
