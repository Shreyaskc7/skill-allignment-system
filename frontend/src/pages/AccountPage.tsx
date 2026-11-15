import { useState, type FormEvent } from 'react';
import { errorMessage, postJson, setAccessToken } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { PasswordField, SubmitButton, useToast } from '../components/ui';
import { passwordProblem } from './auth/passwordRules';

export function AccountPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!current) found.current = 'Enter your current password';
    const pw = passwordProblem(next);
    if (pw) found.next = pw;
    else if (next === current) found.next = 'Choose a different password';
    if (confirm !== next) found.confirm = 'Passwords do not match';
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const s = await postJson<{ access_token: string }>('/api/v1/auth/change-password', {
        current_password: current,
        new_password: next,
        confirm_new_password: confirm,
      });
      setAccessToken(s.access_token);
      setCurrent('');
      setNext('');
      setConfirm('');
      toast('success', 'Password changed. You have been signed out on other devices.');
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel narrow">
      <h2>Account security</h2>
      <p className="muted">
        Signed in as <b>{user?.email}</b>
        {user?.last_login_at && <> · last sign-in {new Date(user.last_login_at).toLocaleString()}</>}
      </p>
      <h3>Change password</h3>
      <form onSubmit={submit} noValidate>
        <PasswordField label="Current password" autoComplete="current-password" value={current}
          onChange={(e) => setCurrent(e.target.value)} error={errors.current} />
        <PasswordField label="New password" autoComplete="new-password" value={next}
          onChange={(e) => setNext(e.target.value)} error={errors.next}
          hint="At least 8 characters, with letters and numbers." />
        <PasswordField label="Confirm new password" autoComplete="new-password" value={confirm}
          onChange={(e) => setConfirm(e.target.value)} error={errors.confirm} />
        <SubmitButton busy={busy}>Change password</SubmitButton>
      </form>
    </section>
  );
}
