import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, BookOpen, Briefcase, CheckCircle2, ClipboardList, Target } from 'lucide-react';
import { errorMessage, putJson, request } from '../api/client';
import { useApp } from '../components/AppLayout';
import { Empty, Metric } from '../components/common';
import { Alert, LoadingScreen, useToast } from '../components/ui';
import type { MentoringNote, StudentDashboard } from '../types';

type Mentoring = { mentors: { full_name: string; email: string }[]; notes: MentoringNote[] };

export function StudentDashboardPage() {
  const { data } = useApp();
  const toast = useToast();
  const [d, setD] = useState<StudentDashboard | null>(null);
  const [error, setError] = useState('');
  const [mentoring, setMentoring] = useState<Mentoring | null>(null);

  const load = useCallback(() => {
    request<StudentDashboard>('/api/v1/students/me/dashboard')
      .then(setD)
      .catch((e) => setError(errorMessage(e)));
    request<Mentoring>('/api/v1/students/me/mentoring').then(setMentoring).catch(() => setMentoring(null));
  }, []);
  // Reload whenever the shared data reloads (e.g. after an assessment or progress update).
  useEffect(load, [load, data.progress]);

  async function chooseCareer(id: string) {
    try {
      await putJson('/api/v1/students/me/target-career', { target_career_id: id ? Number(id) : null });
      if (id) data.setRole(id); // keep the Skill Gaps page in step
      load();
      toast('success', 'Target career saved.');
    } catch (e) {
      toast('error', errorMessage(e));
    }
  }

  if (error) return <Alert>{error}</Alert>;
  if (!d) return <LoadingScreen />;

  const tc = d.target_career;
  const score = tc?.alignment_score ?? 0;
  const firstName = d.user.full_name.split(' ')[0];
  const topDemand = data.analytics[0]?.postings || 1;

  return (
    <>
      <section className="hero">
        <div>
          <label>WELCOME BACK, {firstName.toUpperCase()}</label>
          <h2>
            {tc ? (
              <>
                Your path to
                <br />
                <em>{tc.name}.</em>
              </>
            ) : (
              <>
                Choose a target career
                <br />
                <em>to see your alignment.</em>
              </>
            )}
          </h2>
          <p>
            {tc
              ? `You meet ${tc.skills_met} of ${tc.skills_total} required skills based on your assessments.`
              : 'Pick the role you are working toward. Your assessments are compared with its skill requirements.'}
          </p>
          <Link to="/app/assessment" className="primary">Take an assessment →</Link>
        </div>
        <div className="hero-score">
          <span>CAREER ALIGNMENT</span>
          <strong>
            {tc ? score : '–'}
            <small>{tc ? '%' : ''}</small>
          </strong>
          <div className="progress">
            <i style={{ width: `${score}%` }} />
          </div>
          <select className="hero-select" aria-label="Target career" value={tc?.id ?? ''}
            onChange={(e) => chooseCareer(e.target.value)}>
            <option value="">Select a target career…</option>
            {data.careers.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <small>Rule-based weighted score, not a hiring prediction.</small>
        </div>
      </section>

      {d.profile_completion.percent < 100 && (
        <section className="panel completion-card">
          <div>
            <h3>Complete your profile ({d.profile_completion.percent}%)</h3>
            <p className="muted">Missing: {d.profile_completion.missing.join(', ')}.</p>
          </div>
          <div className="progress"><i style={{ width: `${d.profile_completion.percent}%` }} /></div>
          <Link to="/app/profile" className="secondary">Update profile</Link>
        </section>
      )}

      <div className="metrics">
        <Metric icon={<ClipboardList />} label="Assessments taken" value={d.assessments.count} />
        <Metric icon={<Target />} label="Average score"
          value={d.assessments.average_score == null ? '–' : `${d.assessments.average_score}%`} />
        <Metric icon={<CheckCircle2 />} label="Resources completed" value={d.learning.completed} />
        <Metric icon={<Activity />} label="In progress" value={d.learning.in_progress} />
      </div>

      <div className="grid2">
        <section className="panel">
          <h3>Skills to develop</h3>
          <p className="muted">{tc ? `Gaps for ${tc.name}, highest priority first.` : 'Select a target career first.'}</p>
          {tc?.missing_skills.slice(0, 6).map((x) => (
            <div className="gaprow" key={x.skill_id}>
              <div>
                <b>{x.skill}</b>
                <small>
                  {x.assessed ? `Assessed ${x.current_level}/5` : 'Not assessed yet'} · Required {x.required_level}/5 ·
                  Weight {x.importance}
                </small>
              </div>
              <span className={'pill ' + (x.priority === 'High' ? 'high' : '')}>{x.priority}</span>
            </div>
          ))}
          {tc && !tc.missing_skills.length && <Empty text="You meet every requirement for this role." />}
          {tc && tc.missing_skills.length > 6 && <Link to="/app/skill-gaps" className="more-link">See all gaps →</Link>}
        </section>

        <section className="panel">
          <h3>Assessed skills</h3>
          <p className="muted">
            Proven by assessments. {d.self_reported_skill_count} self-reported skill(s) are kept separately on your profile.
          </p>
          {d.assessed_skills.map((s) => (
            <div className="barrow" key={s.skill_id}>
              <span>{s.skill}</span>
              <div className="bar"><i style={{ width: `${(s.level / 5) * 100}%` }} /></div>
              <b>{s.level}/5</b>
            </div>
          ))}
          {!d.assessed_skills.length && <Empty text="Take an assessment to add verified skills." />}
        </section>

        <section className="panel">
          <h3>Recommended resources</h3>
          <p className="muted">Free resources for your highest-priority gaps.</p>
          {d.recommended_resources.map((r) => (
            <div className="gaprow" key={r.id}>
              <div>
                <b>{r.title}</b>
                <small>{r.skill} · {r.provider} · {r.type}{r.status === 'in_progress' ? ' · in progress' : ''}</small>
              </div>
              <a href={r.url} target="_blank" rel="noreferrer" className="link-button">Open ↗</a>
            </div>
          ))}
          {!d.recommended_resources.length && (
            <Empty text={tc ? 'No open resources for your current gaps.' : 'Select a target career to get recommendations.'} />
          )}
        </section>

        <section className="panel">
          <h3>Recent activity</h3>
          <p className="muted">Your latest assessments and learning updates.</p>
          {d.recent_activity.map((a, i) => (
            <div className="gaprow" key={i}>
              <div>
                <b>{a.text}</b>
                <small>{new Date(a.at).toLocaleString()}</small>
              </div>
              {a.type === 'assessment' ? <ClipboardList size={16} /> : <BookOpen size={16} />}
            </div>
          ))}
          {!d.recent_activity.length && <Empty text="No activity yet." />}
        </section>

        <section className="panel">
          <h3>Mentor feedback</h3>
          <p className="muted">
            {mentoring?.mentors.length
              ? `Your mentor: ${mentoring.mentors.map((m) => m.full_name).join(', ')}`
              : 'No mentor assigned yet.'}
          </p>
          {mentoring?.notes.slice(0, 4).map((n) => (
            <div className="note" key={n.id}>
              <div className="note-meta"><b>{n.teacher_name}</b> · {new Date(n.created_at).toLocaleDateString()}</div>
              <p>{n.note}</p>
              {n.resource && <a href={n.resource.url} target="_blank" rel="noreferrer" className="link-button">{n.resource.title} ↗</a>}
            </div>
          ))}
          {mentoring && !mentoring.notes.length && <Empty text="No feedback yet." />}
        </section>

        <section className="panel">
          <h3>Matching jobs</h3>
          <p className="muted">Best matches among {d.matching_jobs.total_jobs} posting(s), by your assessed skills.</p>
          {d.matching_jobs.top.map((j) => (
            <div className="gaprow" key={j.id}>
              <div>
                <Link to={`/app/jobs/${j.id}`} className="table-link">{j.title}</Link>
                <small>
                  {[j.company, j.location].filter(Boolean).join(' · ')}
                  {j.missing_skills.length > 0 && ` · missing ${j.missing_skills.join(', ')}`}
                </small>
              </div>
              <span className="scorechip">{j.match_percent}%</span>
            </div>
          ))}
          {!d.matching_jobs.top.length && (
            <Empty text={d.matching_jobs.total_jobs ? 'No matches yet: take assessments to unlock job matches.' : 'No job postings yet.'} />
          )}
          <Link to="/app/jobs" className="more-link">All jobs →</Link>
        </section>

        <section className="panel">
          <h3>Most requested skills</h3>
          <p className="muted">Extracted from imported job postings.</p>
          {data.analytics.slice(0, 6).map((x) => (
            <div className="barrow" key={x.skill}>
              <span>{x.skill}</span>
              <div className="bar"><i style={{ width: `${Math.max(5, (x.postings / topDemand) * 100)}%` }} /></div>
              <b>{x.postings}</b>
            </div>
          ))}
          {!data.analytics.length && (
            <Empty text="No job postings imported yet." />
          )}
          <Link to="/app/jobs" className="more-link"><Briefcase size={14} /> Job market</Link>
        </section>
      </div>
    </>
  );
}
