import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Pencil, Plus, Search } from 'lucide-react';
import { ApiError, errorMessage, postJson, putJson, request } from '../../api/client';
import { useApp } from '../../components/AppLayout';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { BankQuestion } from '../../types';

type Page = { items: BankQuestion[]; total: number; page: number; total_pages: number };
const EMPTY = { skill_id: '', question: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_option: 'A',
  explanation: '', difficulty: 'beginner', topic: '', subtopic: '' };

export function QuestionBankPage() {
  const { data } = useApp();
  const toast = useToast();
  const [skill, setSkill] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [active, setActive] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [res, setRes] = useState<Page | null>(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<BankQuestion | 'new' | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), page_size: '20' });
    if (skill) p.set('skill_id', skill);
    if (difficulty) p.set('difficulty', difficulty);
    if (active) p.set('active', active);
    if (search.trim()) p.set('search', search.trim());
    request<Page>(`/api/v1/question-bank/questions?${p}`).then(setRes).catch((e) => setError(errorMessage(e)));
  }, [page, skill, difficulty, active, search]);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  useEffect(() => setPage(1), [skill, difficulty, active, search]);

  function open(q: BankQuestion | 'new') {
    setEditing(q);
    setErrors({});
    setForm(q === 'new' ? { ...EMPTY, skill_id: skill } : Object.fromEntries(
      Object.keys(EMPTY).map((k) => [k, String((q as Record<string, unknown>)[k] ?? '')])));
  }

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!form.skill_id) found.skill_id = 'Choose a skill';
    for (const k of ['question', 'option_a', 'option_b', 'option_c', 'option_d', 'explanation']) {
      if (!form[k].trim()) found[k] = 'Required';
    }
    const opts = ['option_a', 'option_b', 'option_c', 'option_d'].map((k) => form[k].trim());
    if (opts.every(Boolean) && new Set(opts).size !== 4) found.option_d = 'The four options must be different';
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    const body = { ...form, skill_id: Number(form.skill_id), topic: form.topic.trim() || null, subtopic: form.subtopic.trim() || null };
    try {
      if (editing === 'new') await postJson('/api/v1/question-bank/questions', body);
      else if (editing) await putJson(`/api/v1/question-bank/questions/${editing.id}`, body);
      toast('success', editing === 'new' ? 'Question added.' : 'Question updated.');
      setEditing(null);
      load();
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(q: BankQuestion) {
    try {
      await putJson(`/api/v1/question-bank/questions/${q.id}`, { is_active: !q.is_active });
      toast('success', q.is_active ? 'Question disabled; it will no longer be delivered.' : 'Question enabled.');
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  const input = (k: string, label: string, area = false) => (
    <div className={'field' + (errors[k] ? ' has-error' : '')}>
      <label htmlFor={`qb-${k}`}>{label}</label>
      {area ? <textarea id={`qb-${k}`} rows={3} value={form[k]} onChange={set(k)} />
        : <input id={`qb-${k}`} value={form[k]} onChange={set(k)} />}
      {errors[k] && <small className="field-error">{errors[k]}</small>}
    </div>
  );

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h2>Question bank {res && <small className="muted">({res.total})</small>}</h2>
          <button className="primary" onClick={() => open('new')}><Plus size={16} /> New question</button>
        </div>
        <div className="filters">
          <label className="search">
            <Search size={15} aria-hidden="true" />
            <input aria-label="Search questions" placeholder="Search text or topic" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <select aria-label="Skill" value={skill} onChange={(e) => setSkill(e.target.value)}>
            <option value="">All skills</option>
            {data.skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select aria-label="Difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option value="">All levels</option><option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
          </select>
          <select aria-label="Status" value={active} onChange={(e) => setActive(e.target.value)}>
            <option value="">Active and disabled</option><option value="true">Active</option><option value="false">Disabled</option>
          </select>
        </div>
        {error && <Alert>{error}</Alert>}
        {!res && !error && <LoadingScreen />}
        {res && !res.items.length && <Empty text="No questions match these filters." />}
        {res && res.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Question</th><th>Skill</th><th>Level</th><th>Answer</th><th>Status</th><th aria-label="Actions" /></tr></thead>
              <tbody>
                {res.items.map((q) => (
                  <tr key={q.id} className={q.is_active ? '' : 'inactive'}>
                    <td className="q-cell"><span className="q-text">{q.question}</span>{q.topic && <small className="cell-sub">{q.topic}</small>}</td>
                    <td>{q.skill}</td>
                    <td><span className={`pill diff-${q.difficulty}`}>{q.difficulty}</span></td>
                    <td>{q.correct_option}</td>
                    <td>
                      <button className={'link-button' + (q.is_active ? ' danger' : '')} onClick={() => toggle(q)}>
                        {q.is_active ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                    <td><button className="icon-button" aria-label="Edit question" onClick={() => open(q)}><Pencil size={15} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {res && res.total_pages > 1 && (
          <div className="pager">
            <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span>Page {res.page} of {res.total_pages}</span>
            <button className="secondary" disabled={page >= res.total_pages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </section>

      {editing && (
        <div className="dialog-backdrop" onClick={() => setEditing(null)}>
          <form className="dialog wide-dialog" role="dialog" aria-modal="true" aria-labelledby="qb-title"
            onClick={(e) => e.stopPropagation()} onSubmit={save} noValidate>
            <h3 id="qb-title">{editing === 'new' ? 'New question' : 'Edit question'}</h3>
            {editing !== 'new' && <p className="muted small">Past attempts keep the version their students saw.</p>}
            <div className="form-grid">
              <div className={'field' + (errors.skill_id ? ' has-error' : '')}>
                <label htmlFor="qb-skill">Skill</label>
                <select id="qb-skill" value={form.skill_id} onChange={set('skill_id')} disabled={editing !== 'new'}>
                  <option value="">Choose…</option>
                  {data.skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                {errors.skill_id && <small className="field-error">{errors.skill_id}</small>}
              </div>
              <div className="field">
                <label htmlFor="qb-diff">Difficulty</label>
                <select id="qb-diff" value={form.difficulty} onChange={set('difficulty')}>
                  <option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
                </select>
              </div>
            </div>
            {input('question', 'Question', true)}
            <div className="form-grid">
              {input('option_a', 'Option A')}{input('option_b', 'Option B')}{input('option_c', 'Option C')}{input('option_d', 'Option D')}
              <div className="field">
                <label htmlFor="qb-correct">Correct option</label>
                <select id="qb-correct" value={form.correct_option} onChange={set('correct_option')}>
                  {['A', 'B', 'C', 'D'].map((x) => <option key={x}>{x}</option>)}
                </select>
              </div>
              {input('topic', 'Topic')}
            </div>
            {input('explanation', 'Explanation (shown after submission)', true)}
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button type="submit" className="primary" disabled={busy}>{busy && <Spinner />} Save</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
