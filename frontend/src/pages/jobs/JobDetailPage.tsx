import { useEffect, useState } from 'react';
import { safeUrl } from '../../api/safeUrl';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, CircleDashed, ExternalLink, XCircle } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { Alert, LoadingScreen } from '../../components/ui';
import type { Job, JobSkillMatch } from '../../types';
import { MatchBadge, experienceText, salaryText } from './JobMarketPage';

function SkillLine({ s, student }: { s: JobSkillMatch; student: boolean }) {
  return (
    <div className="gaprow">
      <div>
        <b>{student && (s.has ? <CheckCircle2 size={14} className="ok-icon" /> : <XCircle size={14} className="bad-icon" />)} {s.skill}</b>
        {student && <small>{s.your_level == null ? 'Not assessed yet' : `Your assessed level ${s.your_level}/5`} · needs 3/5 to count</small>}
      </div>
      {student && !s.has && <Link to="/app/assessment" className="link-button">{s.your_level == null ? 'Assess' : 'Improve'} →</Link>}
    </div>
  );
}

export function JobDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const student = user!.role === 'student';
  const [j, setJ] = useState<Job | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    request<Job>(`/api/v1/jobs/${id}`).then(setJ).catch((e) => setError(errorMessage(e)));
  }, [id]);
  if (error) return <Alert>{error}</Alert>;
  if (!j) return <LoadingScreen />;

  return (
    <>
      <Link to="/app/jobs" className="more-link back"><ArrowLeft size={14} /> All jobs</Link>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>{j.title}</h2>
            <p className="muted">
              {[j.company, j.location, j.employment_type, experienceText(j), salaryText(j)].filter(Boolean).join(' · ')}
              {j.posted_on && ` · posted ${new Date(j.posted_on).toLocaleDateString()}`} · source: {j.source}
            </p>
          </div>
          {student && <MatchBadge value={j.match_percent} />}
        </div>
        {student && <Alert kind="info">{j.match_rule} A high match does not guarantee selection.</Alert>}
        <p className="job-description">{j.description}</p>
        {j.application_url && (
          <a href={safeUrl(j.application_url)} target="_blank" rel="noreferrer noopener" className="primary">Apply on employer site <ExternalLink size={14} /></a>
        )}
      </section>
      <div className="grid2">
        <section className="panel">
          <h3>Required skills ({j.required.length})</h3>
          {j.required.map((s) => <SkillLine key={s.skill} s={s} student={student} />)}
          {!j.required.length && <p className="muted"><CircleDashed size={14} /> No catalogue skills were recognised in this posting.</p>}
        </section>
        <section className="panel">
          <h3>Nice to have ({j.optional.length})</h3>
          {j.optional.map((s) => <SkillLine key={s.skill} s={s} student={student} />)}
          {!j.optional.length && <p className="muted">None listed.</p>}
        </section>
      </div>
    </>
  );
}
