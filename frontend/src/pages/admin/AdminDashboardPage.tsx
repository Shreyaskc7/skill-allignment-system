import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Briefcase, ClipboardList, GraduationCap, Link2, ListChecks, MailPlus, Shield, Target, Users } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { Metric } from '../../components/common';
import { Alert, LoadingScreen } from '../../components/ui';

type Stats = {
  users: Record<'student' | 'teacher' | 'admin', number>;
  inactive_users: number;
  pending_invitations: number;
  active_assignments: number;
  assessments_total: number;
  assessments_last_30_days: number;
  average_score: number;
  skills: number;
  career_roles_active: number;
  questions_active: number;
  resources: number;
  jobs_active: number;
  logins_last_30_days: number;
};

type AuditItem = { id: number; action: string; user_email: string | null; entity_type: string | null; entity_id: number | null; created_at: string };

export function AdminDashboardPage() {
  const [s, setS] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<AuditItem[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    request<Stats>('/api/v1/admin/stats').then(setS).catch((e) => setError(errorMessage(e)));
    request<{ items: AuditItem[] }>('/api/v1/admin/audit?page_size=8').then((r) => setRecent(r.items)).catch(() => {});
  }, []);
  if (error) return <Alert>{error}</Alert>;
  if (!s) return <LoadingScreen />;

  return (
    <>
      <div className="metrics">
        <Metric icon={<GraduationCap />} label="Active students" value={s.users.student} />
        <Metric icon={<Users />} label="Active mentors" value={s.users.teacher} />
        <Metric icon={<Shield />} label="Administrators" value={s.users.admin} />
        <Metric icon={<Link2 />} label="Active assignments" value={s.active_assignments} />
      </div>
      <div className="metrics">
        <Metric icon={<ClipboardList />} label={`Assessments (30 days: ${s.assessments_last_30_days})`} value={s.assessments_total} />
        <Metric icon={<Target />} label="Average score" value={`${s.average_score}%`} />
        <Metric icon={<Briefcase />} label="Active job postings" value={s.jobs_active} />
        <Metric icon={<BookOpen />} label="Learning resources" value={s.resources} />
      </div>
      <div className="grid2">
        <section className="panel">
          <h3>Catalogue and content</h3>
          <div className="gaprow"><div><b>{s.skills} skills · {s.career_roles_active} active career roles</b><small>Requirements drive every alignment score</small></div><Link to="/app/admin/catalogue" className="link-button">Manage →</Link></div>
          <div className="gaprow"><div><b>{s.questions_active} active questions</b><small>Assessment question bank</small></div><Link to="/app/question-bank" className="link-button">Manage →</Link></div>
          <div className="gaprow"><div><b>{s.pending_invitations} pending mentor invitation(s)</b><small>{s.inactive_users} deactivated account(s)</small></div><Link to="/app/admin/users" className="link-button">Users →</Link></div>
          <div className="gaprow"><div><b>Invite a mentor</b><small>Mentor accounts are created only by invitation</small></div><Link to="/app/admin/invitations" className="link-button"><MailPlus size={14} /> Invite</Link></div>
        </section>
        <section className="panel">
          <h3>Recent activity</h3>
          <p className="muted">{s.logins_last_30_days} sign-in(s) in the last 30 days.</p>
          {recent.map((a) => (
            <div className="gaprow" key={a.id}>
              <div><b className="mono">{a.action}</b><small>{a.user_email ?? 'system'} · {new Date(a.created_at).toLocaleString()}</small></div>
            </div>
          ))}
          <Link to="/app/admin/audit" className="more-link"><ListChecks size={14} /> Full audit log</Link>
        </section>
      </div>
    </>
  );
}
