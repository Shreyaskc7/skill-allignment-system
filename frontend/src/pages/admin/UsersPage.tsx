import { useCallback, useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { Role } from '../../types';

type Account = { id: number; email: string; full_name: string; role: Role; is_active: boolean; created_at: string; last_login_at: string | null };
type Page = { items: Account[]; total: number; page: number; total_pages: number };
type Pending = { user: Account; change: { is_active?: boolean; role?: Role } };

export function UsersPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [role, setRole] = useState('');
  const [active, setActive] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [res, setRes] = useState<Page | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: '20' });
    if (role) p.set('role', role);
    if (active) p.set('active', active);
    if (search.trim()) p.set('search', search.trim());
    request<Page>(`/api/v1/admin/accounts?${p}`).then(setRes).catch((e) => setError(errorMessage(e)));
  }, [page, role, active, search]);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  useEffect(() => setPage(1), [role, active, search]);

  async function apply() {
    if (!pending) return;
    setBusy(true);
    try {
      await request(`/api/v1/admin/accounts/${pending.user.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...pending.change, reason: reason.trim() || null }),
      });
      toast('success', `${pending.user.full_name} updated.`);
      setPending(null);
      setReason('');
      load();
    } catch (e) {
      toast('error', errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const describe = (p: Pending) =>
    p.change.is_active === false ? `Deactivate ${p.user.full_name}? They will be signed out everywhere and cannot sign in.`
      : p.change.is_active ? `Reactivate ${p.user.full_name}?`
        : `Change ${p.user.full_name}'s role from ${p.user.role} to ${p.change.role}? Active mentor assignments that no longer fit the role are ended (history is kept).`;

  return (
    <section className="panel">
      <div className="panel-head"><h2>Users {res && <small className="muted">({res.total})</small>}</h2></div>
      <div className="filters">
        <label className="search"><Search size={15} aria-hidden="true" />
          <input aria-label="Search users" placeholder="Name or email" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
        <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">All roles</option><option value="student">Students</option><option value="teacher">Mentors</option><option value="admin">Administrators</option>
        </select>
        <select aria-label="Status" value={active} onChange={(e) => setActive(e.target.value)}>
          <option value="">Active and deactivated</option><option value="true">Active</option><option value="false">Deactivated</option>
        </select>
      </div>
      {error && <Alert>{error}</Alert>}
      {!res && !error && <LoadingScreen />}
      {res && !res.items.length && <Empty text="No users match these filters." />}
      {res && res.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Last sign-in</th><th aria-label="Actions" /></tr></thead>
            <tbody>
              {res.items.map((u) => (
                <tr key={u.id} className={u.is_active ? '' : 'inactive'}>
                  <td>{u.full_name}{u.id === me?.id && ' (you)'}<small className="cell-sub">{u.email}</small></td>
                  <td>
                    <select aria-label={`Role for ${u.full_name}`} value={u.role} disabled={u.id === me?.id}
                      onChange={(e) => setPending({ user: u, change: { role: e.target.value as Role } })}>
                      <option value="student">student</option><option value="teacher">teacher</option><option value="admin">admin</option>
                    </select>
                  </td>
                  <td><span className={'pill' + (u.is_active ? '' : ' status-revoked')}>{u.is_active ? 'active' : 'deactivated'}</span></td>
                  <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'never'}</td>
                  <td>
                    {u.id !== me?.id && (
                      <button className={'link-button' + (u.is_active ? ' danger' : '')}
                        onClick={() => setPending({ user: u, change: { is_active: !u.is_active } })}>
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {res && res.total_pages > 1 && (
        <div className="pager">
          <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <span>Page {res.page} of {res.total_pages}</span>
          <button className="secondary" disabled={page >= res.total_pages} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      )}

      {pending && (
        <div className="dialog-backdrop" onClick={() => setPending(null)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="u-title" onClick={(e) => e.stopPropagation()}>
            <h3 id="u-title">Confirm change</h3>
            <div className="dialog-body">{describe(pending)}</div>
            <div className="field" style={{ marginTop: 12 }}>
              <label htmlFor="u-reason">Reason (recorded in the audit log)</label>
              <input id="u-reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} autoFocus />
            </div>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setPending(null)}>Cancel</button>
              <button className={'primary' + (pending.change.is_active === false ? ' danger' : '')} disabled={busy} onClick={apply}>
                {busy && <Spinner />} Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
