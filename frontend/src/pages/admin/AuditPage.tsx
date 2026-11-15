import { useCallback, useEffect, useState } from 'react';
import { errorMessage, request } from '../../api/client';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen } from '../../components/ui';

type Item = {
  id: number; action: string; user_id: number | null; user_email: string | null; entity_type: string | null;
  entity_id: number | null; details: Record<string, unknown> | null; ip_address: string | null; created_at: string;
};
type Page = { items: Item[]; total: number; page: number; total_pages: number };

const PREFIXES = ['', 'auth.', 'admin.', 'mentor.', 'question.', 'jobs.', 'student.', 'teacher.'];

export function AuditPage() {
  const [action, setAction] = useState('');
  const [page, setPage] = useState(1);
  const [res, setRes] = useState<Page | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: '50' });
    if (action) p.set('action', action);
    request<Page>(`/api/v1/admin/audit?${p}`).then(setRes).catch((e) => setError(errorMessage(e)));
  }, [page, action]);
  useEffect(load, [load]);
  useEffect(() => setPage(1), [action]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Audit log {res && <small className="muted">({res.total})</small>}</h2>
        <select aria-label="Event type" value={action} onChange={(e) => setAction(e.target.value)}>
          {PREFIXES.map((p) => <option key={p} value={p}>{p ? `${p}*` : 'All events'}</option>)}
        </select>
      </div>
      <p className="muted">Security-relevant and administrative actions. Passwords and tokens are never recorded.</p>
      {error && <Alert>{error}</Alert>}
      {!res && !error && <LoadingScreen />}
      {res && !res.items.length && <Empty text="No events." />}
      {res && res.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Event</th><th>By</th><th>Target</th><th>Details</th></tr></thead>
            <tbody>
              {res.items.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                  <td className="mono">{a.action}</td>
                  <td>{a.user_email ?? '—'}{a.ip_address && <small className="cell-sub">{a.ip_address}</small>}</td>
                  <td>{a.entity_type ? `${a.entity_type} #${a.entity_id}` : '—'}</td>
                  <td className="details-cell">{a.details ? JSON.stringify(a.details) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {res && res.total_pages > 1 && (
        <div className="pager">
          <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Newer</button>
          <span>Page {res.page} of {res.total_pages}</span>
          <button className="secondary" disabled={page >= res.total_pages} onClick={() => setPage((p) => p + 1)}>Older</button>
        </div>
      )}
    </section>
  );
}
