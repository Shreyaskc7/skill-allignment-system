import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, errorMessage } from '../../api/client';
import { useAuth, type RegisterInput } from '../../auth/AuthContext';
import { Alert, Field, PasswordField, SubmitButton } from '../../components/ui';
import { AuthLayout } from './AuthLayout';
import { passwordProblem } from './passwordRules';

const EMPTY: RegisterInput = {
  full_name: '',
  email: '',
  phone: '',
  password: '',
  confirm_password: '',
  terms_accepted: false,
};

function validate(f: RegisterInput): Record<string, string> {
  const e: Record<string, string> = {};
  if (f.full_name.trim().length < 2) e.full_name = 'Enter your full name';
  if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) e.email = 'Enter a valid email address';
  if (f.phone && !/^[0-9+()\-\s]{6,30}$/.test(f.phone)) e.phone = 'Use digits, spaces, +, - or brackets';
  const pw = passwordProblem(f.password);
  if (pw) e.password = pw;
  if (f.confirm_password !== f.password) e.confirm_password = 'Passwords do not match';
  if (!f.terms_accepted) e.terms_accepted = 'You must accept the terms and privacy policy';
  return e;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterInput>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k: keyof RegisterInput) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found = validate(form);
    setErrors(found);
    setError('');
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await register({ ...form, email: form.email.trim() });
      navigate('/login', { replace: true, state: { notice: 'Account created. Please sign in.' } });
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Create your student account"
      subtitle="Assess your skills, find gaps and follow a learning path toward your target career."
      footer={
        <>
          Already registered? <Link to="/login">Sign in</Link>
        </>
      }
    >
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} noValidate>
        <Field label="Full name" autoComplete="name" required value={form.full_name} onChange={set('full_name')}
          error={errors.full_name} />
        <Field label="Email address" type="email" autoComplete="email" required value={form.email}
          onChange={set('email')} error={errors.email} />
        <Field label="Phone number (optional)" type="tel" autoComplete="tel" value={form.phone}
          onChange={set('phone')} error={errors.phone} />
        <PasswordField label="Password" autoComplete="new-password" required value={form.password}
          onChange={set('password')} error={errors.password} hint="At least 8 characters, with letters and numbers." />
        <PasswordField label="Confirm password" autoComplete="new-password" required value={form.confirm_password}
          onChange={set('confirm_password')} error={errors.confirm_password} />
        <label className={'checkbox' + (errors.terms_accepted ? ' has-error' : '')}>
          <input type="checkbox" checked={form.terms_accepted} onChange={set('terms_accepted')}
            aria-invalid={!!errors.terms_accepted} />
          <span>
            I agree to the terms of use and consent to SkillAlign storing my profile, assessment results and
            learning progress for career guidance. My data is visible only to me, my assigned mentor and
            administrators.
          </span>
        </label>
        {errors.terms_accepted && <small className="field-error">{errors.terms_accepted}</small>}
        <SubmitButton busy={busy}>Create account</SubmitButton>
        <p className="muted small center">
          Teachers and mentors join through an invitation from an administrator.
        </p>
      </form>
    </AuthLayout>
  );
}
