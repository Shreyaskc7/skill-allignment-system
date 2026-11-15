import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { homeFor, useAuth } from '../../auth/AuthContext';
import { Alert, Field, PasswordField, SubmitButton } from '../../components/ui';
import { AuthLayout } from './AuthLayout';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string; notice?: string } | null) ?? {};
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const user = await login(email.trim(), password);
      const allowed = from.from && (user.role === 'student' ? true : !from.from.startsWith('/app/assessment'));
      navigate(allowed ? from.from! : homeFor(user), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your SkillAlign workspace."
      footer={
        <>
          New student? <Link to="/register">Create an account</Link>
        </>
      }
    >
      {from.notice && <Alert kind="success">{from.notice}</Alert>}
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} noValidate>
        <Field label="Email address" type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
        <PasswordField label="Password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
        <div className="form-row-end">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <SubmitButton busy={busy}>Sign in</SubmitButton>
      </form>
    </AuthLayout>
  );
}
