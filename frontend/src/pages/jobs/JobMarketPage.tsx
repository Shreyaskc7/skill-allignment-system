import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Info, MapPin, Plus, Search, Upload } from 'lucide-react';
import { ApiError, errorMessage, postJson, request } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { useApp } from '../../components/AppLayout';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { ImportResult, Job, JobPage } from '../../types';

export function MatchBadge({ value }: { value: number | null }) {
  if (value == null) return <span className="pill muted-pill" title="No recognised skills to match">No score</span>;
  const tone = value >= 75 ? 'good' : value >= 40 ? 'mid' : 'low';
  return <span className={`match-badge ${tone}`}>{value}% match</span>;
}

export function salaryText(j: Job) {
  if (j.salary_min == null && j.salary_max == null) return null;
  const fmt = (n: number | null) => (n == null ? '' : n.toLocaleString('en-IN'));
  return `${j.salary_currency ?? ''} ${fmt(j.salary_min)}${j.salary_max != null ? ` – ${fmt(j.salary_max)}` : '+'}`.trim();
}

export function experienceText(j: Job) {
  if (j.experience_min_years == null) return null;
  if (j.experience_max_years === 0 && j.experience_min_years === 0) return 'Freshers';
  return j.experience_max_years == null ? `${j.experience_min_years}+ yrs` : `${j.experience_min_years}–${j.experience_max_years} yrs`;
}

export function JobMarketPage() {
  const { user } = useAuth();
  const { data } = useApp();
  const toast = useToast();
  const isStudent = user!.role === 'student';
  const [search, setSearch] = useState('');
  const [location, setLocation] = useState('');
  const [skillId, setSkillId] = useState('');
  const [minMatch, setMinMatch] = useState('');
  const [sort, setSort] = useState<'relevance' | 'date'>(isStudent ? 'relevance' : 'date');
  const [page, setPage] = useState(1);
  const [res, setRes] = useState<JobPage | null>(null);
  const [error, setError] = useState('');
  const [showRule, setShowRule] = useState(false);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [report, setReport] = useState<ImportResult | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: '10', sort });
    if (search.trim()) p.set('search', search.trim());
    if (location.trim()) p.set('location', location.trim());
    if (skillId) p.set('skill_id', skillId);
    if (minMatch) p.set('min_match', minMatch);
    if (!isStudent) p.set('include_inactive', 'true');
    request<JobPage>(`/api/v1/jobs?${p}`).then(setRes).catch((e) => setError(errorMessage(e)));
  }, [page, sort, search, location, skillId, minMatch, isStudent]);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  useEffect(() => setPage(1), [search, location, skillId, minMatch, sort]);

  async function importCsv(file: File | undefined) {
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await request<ImportResult>('/api/v1/jobs/import-csv', { method: 'POST', body: fd });
      setReport(r);
      toast(r.imported ? 'success' : 'info', `Imported ${r.imported} job(s); skipped ${r.skipped}.`);
      load();
      data.load();
    } catch (e) {
      toast('error', errorMessage(e));
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  return (
    <>
      {!isStudent && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Add job postings</h2>
              <p className="muted">
                Import a CSV (title and description required; optional: company, location, posted_date, employment_type,
                experience, salary_min, salary_max, salary_currency, application_url, skills) or add one posting by hand.
                Only use postings you are permitted to use.
              </p>
            </div>
            <div className="career-actions">
              <input ref={fileInput} type="file" accept=".csv,text/csv" hidden onChange={(e) => importCsv(e.target.files?.[0])} />
              <button className="secondary" onClick={() => fileInput.current?.click()} disabled={importing}>
                {importing ? <Spinner /> : <Upload size={15} />} Import CSV
              </button>
              <button className="primary" onClick={() => setAdding(true)}><Plus size={15} /> Add job</button>
            </div>
          </div>
          <a href="/sample_jobs.csv" download className="link-button">Download sample CSV</a>
          {report && (
            <div className="import-report">
              <Alert kind={report.errors.length ? 'info' : 'success'}>
                {report.imported} imported, {report.skipped} skipped. Skills found: {Object.keys(report.skills_found).join(', ') || 'none'}.
              </Alert>
              {[...report.errors.map((e) => ({ ...e, kind: 'Error' })), ...report.warnings.map((w) => ({ ...w, kind: 'Note' }))]
                .sort((a, b) => a.row - b.row)
                .map((e, i) => <div key={i} className={`report-line ${e.kind.toLowerCase()}`}>Row {e.row} · {e.kind}: {e.message}</div>)}
            </div>
          )}
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Jobs {res && <small className="muted">({res.total})</small>}</h2>
          {isStudent && (
            <button className="link-button" onClick={() => setShowRule((x) => !x)} aria-expanded={showRule}>
              <Info size={14} /> How is the match calculated?
            </button>
          )}
        </div>
        {showRule && res && <Alert kind="info">{res.match_rule} A high match does not guarantee selection.</Alert>}
        <div className="filters">
          <label className="search">
            <Search size={15} aria-hidden="true" />
            <input aria-label="Search title or company" placeholder="Title or company" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label className="search">
            <MapPin size={15} aria-hidden="true" />
            <input aria-label="Location" placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
          <select aria-label="Required skill" value={skillId} onChange={(e) => setSkillId(e.target.value)}>
            <option value="">Any skill</option>
            {data.skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {isStudent && (
            <select aria-label="Minimum match" value={minMatch} onChange={(e) => setMinMatch(e.target.value)}>
              <option value="">Any match</option>
              <option value="25">25%+</option><option value="50">50%+</option><option value="75">75%+</option>
            </select>
          )}
          <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as 'relevance' | 'date')}>
            {isStudent && <option value="relevance">Best match</option>}
            <option value="date">Newest</option>
          </select>
        </div>
        {error && <Alert>{error}</Alert>}
        {!res && !error && <LoadingScreen />}
        {res && !res.items.length && <Empty text={res.total === 0 && !search && !location && !skillId && !minMatch
          ? 'No job postings yet.' : 'No jobs match these filters.'} />}
        {res?.items.map((j) => (
          <Link to={`/app/jobs/${j.id}`} className={'job-card' + (j.is_active ? '' : ' inactive')} key={j.id}>
            <div className="job-main">
              <b>{j.title}</b>
              <small>
                {[j.company, j.location, j.employment_type, experienceText(j), salaryText(j)].filter(Boolean).join(' · ')}
                {j.posted_on && ` · posted ${new Date(j.posted_on).toLocaleDateString()}`}
                {!j.is_active && ' · inactive'}
              </small>
              <div className="tags">
                {j.required.map((s) => <span key={s.skill} className={isStudent ? (s.has ? 'has' : 'missing') : ''}>{s.skill}</span>)}
                {j.optional.map((s) => <span key={s.skill} className="optional">{s.skill} (optional)</span>)}
              </div>
            </div>
            {isStudent && <MatchBadge value={j.match_percent} />}
          </Link>
        ))}
        {res && res.total_pages > 1 && (
          <div className="pager">
            <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span>Page {res.page} of {res.total_pages}</span>
            <button className="secondary" disabled={page >= res.total_pages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </section>

      {adding && <AddJobDialog onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load(); data.load(); }} />}
    </>
  );
}

function AddJobDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [f, setF] = useState<Record<string, string>>({
    title: '', company: '', location: '', description: '', employment_type: '', experience_min_years: '',
    experience_max_years: '', salary_min: '', salary_max: '', salary_currency: 'INR', application_url: '', posted_on: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF((x) => ({ ...x, [k]: e.target.value }));

  async function save(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (f.title.trim().length < 2) found.title = 'Enter a job title';
    if (f.description.trim().length < 20) found.description = 'Describe the role (at least 20 characters)';
    if (f.application_url && !/^https?:\/\/\S+$/.test(f.application_url)) found.application_url = 'Must start with http:// or https://';
    if (f.salary_min && f.salary_max && Number(f.salary_min) > Number(f.salary_max)) found.salary_max = 'Must be at least the minimum';
    setErrors(found);
    if (Object.keys(found).length) return;
    const num = (v: string) => (v === '' ? null : Number(v));
    const str = (v: string) => (v.trim() === '' ? null : v.trim());
    setBusy(true);
    try {
      await postJson('/api/v1/jobs', {
        title: f.title.trim(), company: str(f.company), location: str(f.location), description: f.description.trim(),
        employment_type: str(f.employment_type), experience_min_years: num(f.experience_min_years),
        experience_max_years: num(f.experience_max_years), salary_min: num(f.salary_min), salary_max: num(f.salary_max),
        salary_currency: str(f.salary_currency), application_url: str(f.application_url), posted_on: str(f.posted_on),
      });
      toast('success', 'Job added. Skills were extracted from the description.');
      onSaved();
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const field = (k: string, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div className={'field' + (errors[k] ? ' has-error' : '')}>
      <label htmlFor={`job-${k}`}>{label}</label>
      <input id={`job-${k}`} value={f[k]} onChange={set(k)} {...props} />
      {errors[k] && <small className="field-error">{errors[k]}</small>}
    </div>
  );

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <form className="dialog wide-dialog" role="dialog" aria-modal="true" aria-labelledby="job-title-h"
        onClick={(e) => e.stopPropagation()} onSubmit={save} noValidate>
        <h3 id="job-title-h">Add a job posting</h3>
        <div className="form-grid">
          {field('title', 'Job title')}{field('company', 'Company')}{field('location', 'Location')}
          <div className="field">
            <label htmlFor="job-type">Employment type</label>
            <select id="job-type" value={f.employment_type} onChange={set('employment_type')}>
              <option value="">Not specified</option>
              {['full-time', 'part-time', 'internship', 'contract', 'temporary'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          {field('experience_min_years', 'Experience from (years)', { type: 'number', min: 0, max: 40 })}
          {field('experience_max_years', 'Experience to (years)', { type: 'number', min: 0, max: 40 })}
          {field('salary_min', 'Salary from', { type: 'number', min: 0 })}
          {field('salary_max', 'Salary to', { type: 'number', min: 0 })}
          {field('salary_currency', 'Currency')}{field('posted_on', 'Posted on', { type: 'date' })}
        </div>
        {field('application_url', 'Application link')}
        <div className={'field' + (errors.description ? ' has-error' : '')}>
          <label htmlFor="job-desc">Description (skills are extracted from this text; mark extras as “nice to have”)</label>
          <textarea id="job-desc" rows={5} value={f.description} onChange={set('description')} />
          {errors.description && <small className="field-error">{errors.description}</small>}
        </div>
        <div className="dialog-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary" disabled={busy}>{busy && <Spinner />} Save job</button>
        </div>
      </form>
    </div>
  );
}
