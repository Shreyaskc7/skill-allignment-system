import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage, postJson } from '../../api/client';
import { Alert, PasswordField, SubmitButton } from '../../components/ui';
import { AuthLayout } from './AuthLayout';
import { passwordProblem } from './passwordRules';

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    const pw = passwordProblem(password);
    if (pw) found.password = pw;
    if (confirm !== password) found.confirm = 'Passwords do not match';
    setErrors(found);
    setError('');
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await postJson('/api/v1/auth/reset-password', { token, password, confirm_password: confirm });
      navigate('/login', { replace: true, state: { notice: 'Password changed. Please sign in with your new password.' } });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout title="Reset link missing" footer={<Link to="/forgot-password">Request a new link</Link>}>
        <Alert>This page needs the link from your password-reset email.</Alert>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" footer={<Link to="/login">Back to sign in</Link>}>
      {error && (
        <Alert>
          {error} <Link to="/forgot-password">Request a new link</Link>
        </Alert>
      )}
      <form onSubmit={submit} noValidate>
        <PasswordField label="New password" autoComplete="new-password" value={password}
          onChange={(e) => setPassword(e.target.value)} error={errors.password}
          hint="At least 8 characters, with letters and numbers." />
        <PasswordField label="Confirm new password" autoComplete="new-password" value={confirm}
          onChange={(e) => setConfirm(e.target.value)} error={errors.confirm} />
        <SubmitButton busy={busy}>Update password</SubmitButton>
      </form>
    </AuthLayout>
  );
}
