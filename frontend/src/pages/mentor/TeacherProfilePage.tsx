import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ImagePlus, UserRound } from 'lucide-react';
import { ApiError, errorMessage, putJson, request, requestObjectUrl, uploadFile } from '../../api/client';
import { Alert, Field, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { TeacherProfile } from '../../types';

const KEYS = ['full_name', 'phone', 'qualification', 'institution', 'department', 'designation', 'specialization',
  'years_experience', 'areas_of_expertise', 'biography'] as const;

export function TeacherProfilePage() {
  const toast = useToast();
  const [p, setP] = useState<TeacherProfile | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function apply(x: TeacherProfile) {
    setP(x);
    setForm(Object.fromEntries(KEYS.map((k) => [k, x[k] == null ? '' : String(x[k])])));
  }
  useEffect(() => {
    request<TeacherProfile>('/api/v1/teachers/me/profile').then(apply).catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(() => {
    let url: string | null = null;
    if (p?.has_profile_image) requestObjectUrl('/api/v1/teachers/me/photo').then((u) => setPhoto((url = u)));
    else setPhoto(null);
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [p]);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (form.full_name.trim().length < 2) found.full_name = 'Enter your full name';
    const yrs = Number(form.years_experience);
    if (form.years_experience && (!Number.isInteger(yrs) || yrs < 0 || yrs > 60)) found.years_experience = 'Between 0 and 60';
    if (form.phone && !/^[0-9+()\-\s]{6,30}$/.test(form.phone)) found.phone = 'Use digits, spaces, +, - or brackets';
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const body: Record<string, string | number | null> = Object.fromEntries(
        KEYS.map((k) => [k, form[k].trim() === '' ? null : form[k].trim()]),
      );
      body.years_experience = form.years_experience ? Number(form.years_experience) : null;
      apply(await putJson<TeacherProfile>('/api/v1/teachers/me/profile', body));
      toast('success', 'Profile saved.');
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file?: File) {
    if (!file) return;
    try {
      apply(await uploadFile<TeacherProfile>('/api/v1/teachers/me/photo', file));
      toast('success', 'Photo updated.');
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  if (error) return <Alert>{error}</Alert>;
  if (!p) return <LoadingScreen />;
  const area = (k: string, label: string) => (
    <div className="field"><label htmlFor={`tp-${k}`}>{label}</label>
      <textarea id={`tp-${k}`} rows={3} value={form[k]} onChange={set(k)} /></div>
  );

  return (
    <form onSubmit={save} noValidate>
      <section className="panel profile-head">
        <div className="avatar">{photo ? <img src={photo} alt="Profile photo" /> : <UserRound size={42} aria-hidden="true" />}</div>
        <div className="profile-head-text"><h2>{p.full_name}</h2><p className="muted">{p.email} · Teacher / Mentor</p></div>
        <div className="file-actions">
          <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => upload(e.target.files?.[0])} />
          <button type="button" className="secondary" onClick={() => fileInput.current?.click()}><ImagePlus size={16} /> {p.has_profile_image ? 'Change photo' : 'Add photo'}</button>
        </div>
      </section>
      <section className="panel">
        <h3>Professional details</h3>
        <div className="form-grid">
          <Field label="Full name" value={form.full_name} onChange={set('full_name')} error={errors.full_name} />
          <Field label="Phone" type="tel" value={form.phone} onChange={set('phone')} error={errors.phone} />
          <Field label="Qualification" value={form.qualification} onChange={set('qualification')} />
          <Field label="Institution" value={form.institution} onChange={set('institution')} />
          <Field label="Department" value={form.department} onChange={set('department')} />
          <Field label="Designation" value={form.designation} onChange={set('designation')} />
          <Field label="Specialization" value={form.specialization} onChange={set('specialization')} />
          <Field label="Years of experience" type="number" min={0} max={60} value={form.years_experience}
            onChange={set('years_experience')} error={errors.years_experience} />
          {area('areas_of_expertise', 'Areas of expertise')}
          {area('biography', 'Biography')}
        </div>
      </section>
      <div className="sticky-actions"><button className="primary" type="submit" disabled={busy}>{busy && <Spinner />} Save profile</button></div>
    </form>
  );
}
