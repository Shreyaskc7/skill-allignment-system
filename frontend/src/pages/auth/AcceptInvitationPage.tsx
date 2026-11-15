import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage, postJson, request } from '../../api/client';
import { Alert, Field, LoadingScreen, PasswordField, SubmitButton } from '../../components/ui';
import { AuthLayout } from './AuthLayout';
import { passwordProblem } from './passwordRules';

export function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const navigate = useNavigate();
  const [invite, setInvite] = useState<{ email: string; full_name: string } | null>(null);
  const [loadError, setLoadError] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return setLoadError('This page needs the link from your invitation email.');
    request<{ email: string; full_name: string }>(`/api/v1/auth/invitations/${encodeURIComponent(token)}`)
      .then((inv) => {
        setInvite(inv);
        setName(inv.full_name);
      })
      .catch((e) => setLoadError(errorMessage(e)));
  }, [token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (name.trim().length < 2) found.name = 'Enter your full name';
    const pw = passwordProblem(password);
    if (pw) found.password = pw;
    if (confirm !== password) found.confirm = 'Passwords do not match';
    setErrors(found);
    setError('');
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await postJson('/api/v1/auth/accept-invitation', {
        token,
        full_name: name.trim(),
        password,
        confirm_password: confirm,
      });
      navigate('/login', { replace: true, state: { notice: 'Mentor account created. Please sign in.' } });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <AuthLayout title="Invitation unavailable" footer={<Link to="/login">Go to sign in</Link>}>
        <Alert>{loadError} Ask your administrator for a new invitation.</Alert>
      </AuthLayout>
    );
  }
  if (!invite) return <LoadingScreen label="Checking invitation…" />;

  return (
    <AuthLayout title="Join SkillAlign as a mentor" subtitle={`Invitation for ${invite.email}`}>
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} noValidate>
        <Field label="Full name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)}
          error={errors.name} />
        <PasswordField label="Password" autoComplete="new-password" value={password}
          onChange={(e) => setPassword(e.target.value)} error={errors.password}
          hint="At least 8 characters, with letters and numbers." />
        <PasswordField label="Confirm password" autoComplete="new-password" value={confirm}
          onChange={(e) => setConfirm(e.target.value)} error={errors.confirm} />
        <SubmitButton busy={busy}>Create mentor account</SubmitButton>
      </form>
    </AuthLayout>
  );
}
