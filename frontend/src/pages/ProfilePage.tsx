import { useEffect, useRef, useState, type FormEvent } from 'react';
import { FileText, ImagePlus, Plus, Trash2, Upload, UserRound } from 'lucide-react';
import { ApiError, errorMessage, putJson, request, requestObjectUrl, uploadFile } from '../api/client';
import { useApp } from '../components/AppLayout';
import { Alert, ConfirmDialog, LoadingScreen, Spinner, useToast } from '../components/ui';
import type { ExperienceLevel, SelfSkill, StudentProfile } from '../types';

const EXPERIENCE: ExperienceLevel[] = ['fresher', 'internship', '0-1 years', '1-3 years', '3+ years'];
const LEVELS = ['', 'Beginner', 'Elementary', 'Intermediate', 'Advanced', 'Expert'];

type Form = Record<string, string>;

const TEXT_FIELDS = [
  'full_name', 'phone', 'date_of_birth', 'location', 'college', 'degree', 'department', 'specialization',
  'current_semester', 'graduation_year', 'cgpa', 'career_interests', 'target_job_roles', 'technical_skills',
  'soft_skills', 'preferred_locations', 'experience_level', 'target_career_id',
] as const;

function toForm(p: StudentProfile): Form {
  const f: Form = {};
  for (const k of TEXT_FIELDS) {
    const v = (p as Record<string, unknown>)[k];
    f[k] = v == null ? '' : k === 'date_of_birth' ? String(v).slice(0, 10) : String(v);
  }
  return f;
}

function toBody(f: Form) {
  const num = (v: string) => (v.trim() === '' ? null : Number(v));
  const str = (v: string) => (v.trim() === '' ? null : v.trim());
  return {
    full_name: f.full_name.trim(),
    phone: str(f.phone),
    date_of_birth: f.date_of_birth ? `${f.date_of_birth}T00:00:00Z` : null,
    location: str(f.location),
    college: str(f.college),
    degree: str(f.degree),
    department: str(f.department),
    specialization: str(f.specialization),
    current_semester: num(f.current_semester),
    graduation_year: num(f.graduation_year),
    cgpa: num(f.cgpa),
    career_interests: str(f.career_interests),
    target_job_roles: str(f.target_job_roles),
    technical_skills: str(f.technical_skills),
    soft_skills: str(f.soft_skills),
    preferred_locations: str(f.preferred_locations),
    experience_level: str(f.experience_level),
    target_career_id: num(f.target_career_id),
  };
}

function validate(f: Form): Record<string, string> {
  const e: Record<string, string> = {};
  if (f.full_name.trim().length < 2) e.full_name = 'Enter your full name';
  if (f.phone && !/^[0-9+()\-\s]{6,30}$/.test(f.phone)) e.phone = 'Use digits, spaces, +, - or brackets';
  const sem = Number(f.current_semester);
  if (f.current_semester && (!Number.isInteger(sem) || sem < 1 || sem > 12)) e.current_semester = 'Between 1 and 12';
  const year = Number(f.graduation_year);
  if (f.graduation_year && (!Number.isInteger(year) || year < 1990 || year > 2060)) e.graduation_year = 'Enter a valid year';
  const cgpa = Number(f.cgpa);
  if (f.cgpa && (Number.isNaN(cgpa) || cgpa < 0 || cgpa > 100)) e.cgpa = 'CGPA (0–10) or percentage (0–100)';
  return e;
}

export function ProfilePage() {
  const { data } = useApp();
  const toast = useToast();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [form, setForm] = useState<Form>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState<'' | 'photo' | 'resume'>('');
  const [removing, setRemoving] = useState<'' | 'photo' | 'resume'>('');
  const [skills, setSkills] = useState<SelfSkill[]>([]);
  const [newSkill, setNewSkill] = useState('');
  const [newLevel, setNewLevel] = useState('3');
  const photoInput = useRef<HTMLInputElement>(null);
  const resumeInput = useRef<HTMLInputElement>(null);

  function apply(p: StudentProfile) {
    setProfile(p);
    setForm(toForm(p));
  }

  useEffect(() => {
    Promise.all([
      request<StudentProfile>('/api/v1/students/me/profile'),
      request<SelfSkill[]>('/api/v1/students/me/self-skills'),
    ])
      .then(([p, s]) => {
        apply(p);
        setSkills(s);
      })
      .catch((e) => setLoadError(errorMessage(e)));
  }, []);

  // Load the photo through the authenticated endpoint whenever it changes.
  useEffect(() => {
    let url: string | null = null;
    if (profile?.has_profile_image) {
      requestObjectUrl('/api/v1/students/me/photo').then((u) => {
        url = u;
        setPhotoUrl(u);
      });
    } else setPhotoUrl(null);
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [profile?.has_profile_image, uploading]);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: FormEvent) {
    e.preventDefault();
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length) return toast('error', 'Please correct the highlighted fields.');
    setSaving(true);
    try {
      apply(await putJson<StudentProfile>('/api/v1/students/me/profile', toBody(form)));
      toast('success', 'Profile saved.');
      data.load();
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      toast('error', errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function upload(kind: 'photo' | 'resume', file: File | undefined) {
    if (!file) return;
    setUploading(kind);
    try {
      apply(await uploadFile<StudentProfile>(`/api/v1/students/me/${kind}`, file));
      toast('success', kind === 'photo' ? 'Profile photo updated.' : 'Resume uploaded.');
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setUploading('');
      if (photoInput.current) photoInput.current.value = '';
      if (resumeInput.current) resumeInput.current.value = '';
    }
  }

  async function removeFile(kind: 'photo' | 'resume') {
    setRemoving('');
    try {
      apply(await request<StudentProfile>(`/api/v1/students/me/${kind}`, { method: 'DELETE' }));
      toast('success', kind === 'photo' ? 'Photo removed.' : 'Resume removed.');
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  async function openResume() {
    const url = await requestObjectUrl('/api/v1/students/me/resume');
    if (url) window.open(url, '_blank', 'noopener');
    else toast('error', 'Could not open the resume.');
  }

  async function saveSkills(next: SelfSkill[]) {
    try {
      const saved = await putJson<SelfSkill[]>('/api/v1/students/me/self-skills', {
        skills: next.map((s) => ({ skill_id: s.skill_id, level: s.level })),
      });
      setSkills(saved);
      setProfile(await request<StudentProfile>('/api/v1/students/me/profile'));
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  function addSkill() {
    const s = data.skills.find((x) => x.id === Number(newSkill));
    if (!s) return;
    saveSkills([...skills, { skill_id: s.id, skill_name: s.name, category: s.category, level: Number(newLevel) }]);
    setNewSkill('');
  }

  if (loadError) return <Alert>{loadError}</Alert>;
  if (!profile) return <LoadingScreen />;

  const field = (k: string, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div className={'field' + (errors[k] ? ' has-error' : '')}>
      <label htmlFor={`pf-${k}`}>{label}</label>
      <input id={`pf-${k}`} value={form[k] ?? ''} onChange={set(k)} aria-invalid={!!errors[k]} {...props} />
      {errors[k] && <small className="field-error">{errors[k]}</small>}
    </div>
  );
  const area = (k: string, label: string, placeholder = '') => (
    <div className="field">
      <label htmlFor={`pf-${k}`}>{label}</label>
      <textarea id={`pf-${k}`} rows={2} value={form[k] ?? ''} onChange={set(k)} placeholder={placeholder} />
    </div>
  );
  const available = data.skills.filter((s) => !skills.some((x) => x.skill_id === s.id));

  return (
    <>
      <section className="panel profile-head">
        <div className="avatar">
          {photoUrl ? <img src={photoUrl} alt="Profile photo" /> : <UserRound size={42} aria-hidden="true" />}
        </div>
        <div className="profile-head-text">
          <h2>{profile.full_name}</h2>
          <p className="muted">{profile.email}</p>
          <div className="completion">
            <div className="progress" aria-label={`Profile ${profile.completion.percent}% complete`}>
              <i style={{ width: `${profile.completion.percent}%` }} />
            </div>
            <small>
              Profile {profile.completion.percent}% complete
              {profile.completion.missing.length > 0 && <> · Missing: {profile.completion.missing.join(', ')}</>}
            </small>
          </div>
        </div>
        <div className="file-actions">
          <input ref={photoInput} type="file" accept="image/png,image/jpeg,image/webp" hidden
            onChange={(e) => upload('photo', e.target.files?.[0])} />
          <button className="secondary" onClick={() => photoInput.current?.click()} disabled={!!uploading}>
            {uploading === 'photo' ? <Spinner /> : <ImagePlus size={16} />} {profile.has_profile_image ? 'Change photo' : 'Add photo'}
          </button>
          {profile.has_profile_image && (
            <button className="link-button danger" onClick={() => setRemoving('photo')}>Remove photo</button>
          )}
          <small className="muted small">PNG, JPEG or WebP, up to 2 MB</small>
        </div>
      </section>

      <form onSubmit={save} noValidate>
        <section className="panel">
          <h3>Personal details</h3>
          <div className="form-grid">
            {field('full_name', 'Full name', { autoComplete: 'name' })}
            <div className="field">
              <label htmlFor="pf-email">Email</label>
              <input id="pf-email" value={profile.email} disabled />
            </div>
            {field('phone', 'Phone number', { type: 'tel', autoComplete: 'tel' })}
            {field('date_of_birth', 'Date of birth (optional)', { type: 'date' })}
            {field('location', 'Location', { placeholder: 'City, State' })}
          </div>
        </section>

        <section className="panel">
          <h3>Academic details</h3>
          <div className="form-grid">
            {field('college', 'College / institution')}
            {field('degree', 'Degree', { placeholder: 'e.g. MCA' })}
            {field('department', 'Department')}
            {field('specialization', 'Specialization')}
            {field('current_semester', 'Current semester', { type: 'number', min: 1, max: 12 })}
            {field('graduation_year', 'Graduation year', { type: 'number', min: 1990, max: 2060 })}
            {field('cgpa', 'CGPA or percentage (optional)', { type: 'number', step: '0.01', min: 0, max: 100 })}
          </div>
        </section>

        <section className="panel">
          <h3>Career details</h3>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-target">Target career</label>
              <select id="pf-target" value={form.target_career_id} onChange={set('target_career_id')}>
                <option value="">Not selected</option>
                {data.careers.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="pf-exp">Experience level</label>
              <select id="pf-exp" value={form.experience_level} onChange={set('experience_level')}>
                <option value="">Not specified</option>
                {EXPERIENCE.map((x) => (
                  <option key={x} value={x}>{x}</option>
                ))}
              </select>
            </div>
            {area('career_interests', 'Career interests', 'e.g. backend development, data analytics')}
            {area('target_job_roles', 'Other target job roles')}
            {area('preferred_locations', 'Preferred job locations', 'e.g. Bengaluru, Pune, remote')}
            {area('technical_skills', 'Other technical skills (not listed below)')}
            {area('soft_skills', 'Soft skills')}
          </div>
          <div className="resume-row">
            <FileText size={18} aria-hidden="true" />
            <span>{profile.has_resume ? 'Resume uploaded' : 'No resume uploaded (optional, PDF up to 5 MB)'}</span>
            {profile.has_resume && <button type="button" className="link-button" onClick={openResume}>View</button>}
            <input ref={resumeInput} type="file" accept="application/pdf" hidden
              onChange={(e) => upload('resume', e.target.files?.[0])} />
            <button type="button" className="secondary" onClick={() => resumeInput.current?.click()} disabled={!!uploading}>
              {uploading === 'resume' ? <Spinner /> : <Upload size={15} />} {profile.has_resume ? 'Replace' : 'Upload'}
            </button>
            {profile.has_resume && (
              <button type="button" className="link-button danger" onClick={() => setRemoving('resume')}>Remove</button>
            )}
          </div>
        </section>

        <div className="sticky-actions">
          <button className="primary" type="submit" disabled={saving}>
            {saving && <Spinner />} Save profile
          </button>
        </div>
      </form>

      <section className="panel">
        <h3>Skills and interests (self-reported)</h3>
        <p className="muted">
          Tell us what you believe your level is. These are shown separately and are <b>not</b> counted as proven
          proficiency: only assessments change your career alignment.
        </p>
        {skills.length === 0 && <p className="muted">No skills added yet.</p>}
        <div className="self-skills">
          {skills.map((s) => (
            <div className="self-skill" key={s.skill_id}>
              <div>
                <b>{s.skill_name}</b>
                <small>{s.category}</small>
              </div>
              <select aria-label={`Level for ${s.skill_name}`} value={s.level}
                onChange={(e) => saveSkills(skills.map((x) => (x.skill_id === s.skill_id ? { ...x, level: Number(e.target.value) } : x)))}>
                {[1, 2, 3, 4, 5].map((l) => (
                  <option key={l} value={l}>{l} · {LEVELS[l]}</option>
                ))}
              </select>
              <button className="icon-button" aria-label={`Remove ${s.skill_name}`}
                onClick={() => saveSkills(skills.filter((x) => x.skill_id !== s.skill_id))}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
        <div className="add-skill">
          <select aria-label="Skill to add" value={newSkill} onChange={(e) => setNewSkill(e.target.value)}>
            <option value="">Choose a skill…</option>
            {available.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.category})</option>
            ))}
          </select>
          <select aria-label="Your level" value={newLevel} onChange={(e) => setNewLevel(e.target.value)}>
            {[1, 2, 3, 4, 5].map((l) => (
              <option key={l} value={l}>{l} · {LEVELS[l]}</option>
            ))}
          </select>
          <button className="secondary" onClick={addSkill} disabled={!newSkill}>
            <Plus size={15} /> Add skill
          </button>
        </div>
      </section>

      {removing && (
        <ConfirmDialog
          title={removing === 'photo' ? 'Remove profile photo?' : 'Remove resume?'}
          confirmLabel="Remove" onCancel={() => setRemoving('')} onConfirm={() => removeFile(removing)}>
          The file will be deleted from SkillAlign.
        </ConfirmDialog>
      )}
    </>
  );
}
