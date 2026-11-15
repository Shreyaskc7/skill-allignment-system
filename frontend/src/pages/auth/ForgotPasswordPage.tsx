import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage, postJson } from '../../api/client';
import { Alert, Field, SubmitButton } from '../../components/ui';
import { AuthLayout } from './AuthLayout';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Enter a valid email address');
    setBusy(true);
    try {
      const r = await postJson<{ message: string }>('/api/v1/auth/forgot-password', { email: email.trim() });
      setSent(r.message);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter your account email and we will send you a link to choose a new password."
      footer={<Link to="/login">Back to sign in</Link>}
    >
      {sent ? (
        <Alert kind="success">{sent} The link expires in 30 minutes.</Alert>
      ) : (
        <>
          {error && <Alert>{error}</Alert>}
          <form onSubmit={submit} noValidate>
            <Field label="Email address" type="email" autoComplete="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
            <SubmitButton busy={busy}>Send reset link</SubmitButton>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
