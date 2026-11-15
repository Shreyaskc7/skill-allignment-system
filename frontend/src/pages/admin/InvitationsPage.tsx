import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Copy } from 'lucide-react';
import { ApiError, errorMessage, postJson, request } from '../../api/client';
import { Empty } from '../../components/common';
import { Alert, ConfirmDialog, Field, LoadingScreen, useToast } from '../../components/ui';
import type { Invitation } from '../../types';

export function InvitationsPage() {
  const toast = useToast();
  const [items, setItems] = useState<Invitation[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Invitation | null>(null);
  const [revoking, setRevoking] = useState<Invitation | null>(null);

  const load = useCallback(() => {
    request<Invitation[]>('/api/v1/admin/invitations')
      .then(setItems)
      .catch((e) => setLoadError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (name.trim().length < 2) found.full_name = 'Enter the mentor’s full name';
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) found.email = 'Enter a valid email address';
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const inv = await postJson<Invitation>('/api/v1/admin/invitations', { email: email.trim(), full_name: name.trim() });
      setCreated(inv);
      setEmail('');
      setName('');
      toast('success', `Invitation created for ${inv.email}.`);
      load();
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(inv: Invitation) {
    setRevoking(null);
    try {
      await postJson(`/api/v1/admin/invitations/${inv.id}/revoke`, {});
      toast('success', `Invitation for ${inv.email} revoked.`);
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  return (
    <>
      <section className="panel">
        <h2>Invite a teacher or mentor</h2>
        <p className="muted">
          Mentor accounts cannot be self-registered. The invitee receives a single-use link valid for 7 days. If email
          (SMTP) is not configured, copy the link below and share it securely.
        </p>
        <form className="inline-form" onSubmit={invite} noValidate>
          <Field label="Full name" value={name} onChange={(e) => setName(e.target.value)} error={errors.full_name} />
          <Field label="Email address" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            error={errors.email} />
          <button className="primary" type="submit" disabled={busy}>
            Send invitation
          </button>
        </form>
        {created?.invite_url && (
          <Alert kind="success">
            Invitation link for {created.email}:{' '}
            <code className="invite-link">{created.invite_url}</code>{' '}
            <button
              className="link-button"
              onClick={() => navigator.clipboard.writeText(created.invite_url!).then(() => toast('info', 'Link copied.'))}
            >
              <Copy size={14} /> Copy
            </button>
          </Alert>
        )}
      </section>

      <section className="panel">
        <h2>Invitations</h2>
        {loadError && <Alert>{loadError}</Alert>}
        {!items && !loadError && <LoadingScreen />}
        {items && !items.length && <Empty text="No invitations yet." />}
        {items && items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Expires</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id}>
                    <td>{i.full_name}</td>
                    <td>{i.email}</td>
                    <td>
                      <span className={`pill status-${i.status}`}>{i.status}</span>
                    </td>
                    <td>{new Date(i.expires_at).toLocaleDateString()}</td>
                    <td>
                      {i.status === 'pending' && (
                        <button className="link-button danger" onClick={() => setRevoking(i)}>
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {revoking && (
        <ConfirmDialog title="Revoke invitation?" confirmLabel="Revoke" onCancel={() => setRevoking(null)}
          onConfirm={() => revoke(revoking)}>
          The link sent to <b>{revoking.email}</b> will stop working. You can send a new invitation later.
        </ConfirmDialog>
      )}
    </>
  );
}
