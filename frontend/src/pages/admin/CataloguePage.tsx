import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { safeUrl } from '../../api/safeUrl';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { errorMessage, postJson, putJson, request } from '../../api/client';
import { useApp } from '../../components/AppLayout';
import { Alert, ConfirmDialog, LoadingScreen, Spinner, useToast } from '../../components/ui';

type Tab = 'skills' | 'careers' | 'resources';
type Req = { skill_id: number; required_level: number; importance_weight: number; skill?: string };
type Career = { id: number; name: string; description: string; is_active: boolean; requirements: Req[] };
const RTYPES = ['documentation', 'course', 'tutorial', 'practice', 'project', 'book', 'video', 'certification'];

export function CataloguePage() {
  const [tab, setTab] = useState<Tab>('careers');
  return (
    <>
      <div className="segmented tabs" role="tablist">
        {(['careers', 'skills', 'resources'] as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
            {t === 'careers' ? 'Career roles' : t === 'skills' ? 'Skills' : 'Learning resources'}
          </button>
        ))}
      </div>
      {tab === 'careers' && <CareersTab />}
      {tab === 'skills' && <SkillsTab />}
      {tab === 'resources' && <ResourcesTab />}
    </>
  );
}

// ------------------------------------------------------------------ career roles

function CareersTab() {
  const { data } = useApp();
  const toast = useToast();
  const [items, setItems] = useState<Career[] | null>(null);
  const [edit, setEdit] = useState<Career | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    request<Career[]>('/api/v1/admin/careers').then(setItems).catch((e) => toast('error', errorMessage(e)));
  }, [toast]);
  useEffect(load, [load]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!edit) return;
    if (edit.name.trim().length < 2) return toast('error', 'Enter a role name.');
    if (!edit.requirements.length) return toast('error', 'Add at least one required skill.');
    setBusy(true);
    const body = { name: edit.name.trim(), description: edit.description, is_active: edit.is_active,
      requirements: edit.requirements.map(({ skill_id, required_level, importance_weight }) => ({ skill_id, required_level, importance_weight })) };
    try {
      if (edit.id) await putJson(`/api/v1/admin/careers/${edit.id}`, body);
      else await postJson('/api/v1/admin/careers', body);
      toast('success', 'Career role saved. Alignment scores now use these requirements.');
      setEdit(null);
      load();
      data.load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const setReq = (i: number, k: keyof Req, v: number) =>
    setEdit((c) => c && { ...c, requirements: c.requirements.map((r, j) => (j === i ? { ...r, [k]: v } : r)) });
  const unused = data.skills.filter((s) => !edit?.requirements.some((r) => r.skill_id === s.id));

  if (!items) return <LoadingScreen />;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Career roles</h2>
        <button className="primary" onClick={() => setEdit({ id: 0, name: '', description: '', is_active: true, requirements: [] })}><Plus size={15} /> New role</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Role</th><th>Required skills (level · weight)</th><th>Status</th><th aria-label="Edit" /></tr></thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className={c.is_active ? '' : 'inactive'}>
                <td>{c.name}</td>
                <td className="small">{c.requirements.map((r) => `${r.skill} (${r.required_level}·w${r.importance_weight})`).join(', ')}</td>
                <td><span className={'pill' + (c.is_active ? '' : ' status-revoked')}>{c.is_active ? 'active' : 'hidden'}</span></td>
                <td><button className="icon-button" aria-label={`Edit ${c.name}`} onClick={() => setEdit(structuredClone(c))}><Pencil size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {edit && (
        <div className="dialog-backdrop" onClick={() => setEdit(null)}>
          <form className="dialog wide-dialog" role="dialog" aria-modal="true" aria-labelledby="c-title" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <h3 id="c-title">{edit.id ? `Edit ${edit.name}` : 'New career role'}</h3>
            <div className="field"><label htmlFor="c-name">Name</label>
              <input id="c-name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="c-desc">Description</label>
              <textarea id="c-desc" rows={2} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
            <label className="checkbox inline"><input type="checkbox" checked={edit.is_active}
              onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /><span>Visible to students (active)</span></label>
            <h4>Required skills</h4>
            <p className="muted small">Level 1–5 the role needs, and weight 1–5 for how much the skill counts in the alignment score.</p>
            {edit.requirements.map((r, i) => (
              <div className="req-row" key={r.skill_id}>
                <span>{data.skills.find((s) => s.id === r.skill_id)?.name ?? r.skill}</span>
                <label>Level <select value={r.required_level} onChange={(e) => setReq(i, 'required_level', Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
                <label>Weight <select value={r.importance_weight} onChange={(e) => setReq(i, 'importance_weight', Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
                <button type="button" className="icon-button" aria-label="Remove skill"
                  onClick={() => setEdit({ ...edit, requirements: edit.requirements.filter((_, j) => j !== i) })}><Trash2 size={14} /></button>
              </div>
            ))}
            <select aria-label="Add required skill" value="" onChange={(e) => e.target.value &&
              setEdit({ ...edit, requirements: [...edit.requirements, { skill_id: Number(e.target.value), required_level: 3, importance_weight: 3 }] })}>
              <option value="">+ Add a skill…</option>
              {unused.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={() => setEdit(null)}>Cancel</button>
              <button type="submit" className="primary" disabled={busy}>{busy && <Spinner />} Save role</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ skills

function SkillsTab() {
  const { data } = useApp();
  const toast = useToast();
  const [edit, setEdit] = useState<{ id: number; name: string; category: string; description: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    const body = { name: edit.name, category: edit.category, description: edit.description || null };
    try {
      if (edit.id) await putJson(`/api/v1/admin/skills/${edit.id}`, body);
      else await postJson('/api/v1/admin/skills', body);
      toast('success', 'Skill saved.');
      setEdit(null);
      data.load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Skills ({data.skills.length})</h2>
        <button className="primary" onClick={() => setEdit({ id: 0, name: '', category: '', description: '' })}><Plus size={15} /> New skill</button>
      </div>
      <Alert kind="info">New skills need assessment questions (Question Bank) before students can be assessed in them.</Alert>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Skill</th><th>Category</th><th>Description</th><th aria-label="Edit" /></tr></thead>
          <tbody>
            {data.skills.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td><td>{s.category}</td><td className="small">{s.description}</td>
                <td><button className="icon-button" aria-label={`Edit ${s.name}`}
                  onClick={() => setEdit({ id: s.id, name: s.name, category: s.category, description: s.description ?? '' })}><Pencil size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <div className="dialog-backdrop" onClick={() => setEdit(null)}>
          <form className="dialog" role="dialog" aria-modal="true" aria-labelledby="s-title" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <h3 id="s-title">{edit.id ? 'Edit skill' : 'New skill'}</h3>
            <div className="field"><label htmlFor="s-name">Name</label><input id="s-name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="s-cat">Category</label><input id="s-cat" value={edit.category} onChange={(e) => setEdit({ ...edit, category: e.target.value })} /></div>
            <div className="field"><label htmlFor="s-desc">Description</label><input id="s-desc" value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={() => setEdit(null)}>Cancel</button>
              <button type="submit" className="primary" disabled={busy || !edit.name.trim() || !edit.category.trim()}>{busy && <Spinner />} Save</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ resources

type R = { id: number; skill_id: number; title: string; provider: string; url: string; resource_type: string; difficulty: string; description: string; is_free: boolean };

function ResourcesTab() {
  const { data } = useApp();
  const toast = useToast();
  const [edit, setEdit] = useState<R | null>(null);
  const [deleting, setDeleting] = useState<{ id: number; title: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!edit) return;
    if (!/^https?:\/\/\S+$/.test(edit.url)) return toast('error', 'The link must start with http:// or https://');
    setBusy(true);
    const { id, ...body } = edit;
    try {
      if (id) await putJson(`/api/v1/admin/resources/${id}`, body);
      else await postJson('/api/v1/admin/resources', body);
      toast('success', 'Resource saved.');
      setEdit(null);
      data.load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    try {
      await request(`/api/v1/admin/resources/${deleting.id}`, { method: 'DELETE' });
      toast('success', 'Resource deleted.');
      data.load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setDeleting(null);
    }
  }

  const set = (k: keyof R) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setEdit((x) => x && { ...x, [k]: k === 'skill_id' ? Number(e.target.value) : k === 'is_free' ? (e.target as HTMLInputElement).checked : e.target.value });

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Learning resources ({data.resources.length})</h2>
        <button className="primary" onClick={() => setEdit({ id: 0, skill_id: data.skills[0]?.id ?? 0, title: '', provider: '', url: 'https://', resource_type: 'documentation', difficulty: 'beginner', description: '', is_free: true })}>
          <Plus size={15} /> New resource
        </button>
      </div>
      <p className="muted">Only add legitimate, accessible resources and check the link before saving. Resources with student progress cannot be deleted.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Resource</th><th>Skill</th><th>Type · level</th><th aria-label="Actions" /></tr></thead>
          <tbody>
            {data.resources.map((r) => (
              <tr key={r.id}>
                <td><a href={safeUrl(r.url)} target="_blank" rel="noreferrer noopener" className="table-link">{r.title}</a><small className="cell-sub">{r.provider}</small></td>
                <td>{r.skill}</td><td>{r.type} · {r.difficulty}</td>
                <td className="nowrap">
                  <button className="icon-button" aria-label={`Edit ${r.title}`} onClick={() => setEdit({ id: r.id, skill_id: r.skill_id, title: r.title, provider: r.provider, url: r.url, resource_type: r.type, difficulty: r.difficulty, description: r.description, is_free: r.is_free })}><Pencil size={15} /></button>
                  <button className="icon-button" aria-label={`Delete ${r.title}`} onClick={() => setDeleting({ id: r.id, title: r.title })}><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <div className="dialog-backdrop" onClick={() => setEdit(null)}>
          <form className="dialog wide-dialog" role="dialog" aria-modal="true" aria-labelledby="r-title" onClick={(e) => e.stopPropagation()} onSubmit={save}>
            <h3 id="r-title">{edit.id ? 'Edit resource' : 'New resource'}</h3>
            <div className="form-grid">
              <div className="field"><label htmlFor="r-skill">Skill</label>
                <select id="r-skill" value={edit.skill_id} onChange={set('skill_id')}>{data.skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              <div className="field"><label htmlFor="r-title2">Title</label><input id="r-title2" value={edit.title} onChange={set('title')} /></div>
              <div className="field"><label htmlFor="r-prov">Provider</label><input id="r-prov" value={edit.provider} onChange={set('provider')} /></div>
              <div className="field"><label htmlFor="r-url">Link</label><input id="r-url" value={edit.url} onChange={set('url')} /></div>
              <div className="field"><label htmlFor="r-type">Type</label>
                <select id="r-type" value={edit.resource_type} onChange={set('resource_type')}>{RTYPES.map((t) => <option key={t}>{t}</option>)}</select></div>
              <div className="field"><label htmlFor="r-diff">Difficulty</label>
                <select id="r-diff" value={edit.difficulty} onChange={set('difficulty')}><option>beginner</option><option>intermediate</option><option>advanced</option></select></div>
            </div>
            <div className="field"><label htmlFor="r-desc">Description</label><textarea id="r-desc" rows={2} value={edit.description} onChange={set('description')} /></div>
            <label className="checkbox inline"><input type="checkbox" checked={edit.is_free} onChange={set('is_free')} /><span>Free</span></label>
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={() => setEdit(null)}>Cancel</button>
              <button type="submit" className="primary" disabled={busy || !edit.title.trim() || !edit.provider.trim()}>{busy && <Spinner />} Save</button>
            </div>
          </form>
        </div>
      )}
      {deleting && (
        <ConfirmDialog title="Delete resource?" confirmLabel="Delete" onCancel={() => setDeleting(null)} onConfirm={remove}>
          “{deleting.title}” will be removed permanently. This is refused if any student has progress on it.
        </ConfirmDialog>
      )}
    </section>
  );
}
