import { useEffect, useMemo, useState } from 'react';
import { safeUrl } from '../api/safeUrl';
import { NotebookPen, Search } from 'lucide-react';
import { errorMessage, postJson } from '../api/client';
import { useApp } from '../components/AppLayout';
import { Empty } from '../components/common';
import { Spinner, useToast } from '../components/ui';
import type { ProgressStatus, Resource } from '../types';
import { ResourceActions } from './learning/LearningPathPage';

const TYPES = ['documentation', 'course', 'tutorial', 'practice', 'project', 'book', 'video', 'certification'];

export function LearningResourcesPage({ canTrack }: { canTrack: boolean }) {
  const { data } = useApp();
  const toast = useToast();
  const [skill, setSkill] = useState('');
  const [type, setType] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [noting, setNoting] = useState<Resource | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => setNote(noting?.notes ?? ''), [noting]);

  const shown = useMemo(() => data.resources.filter((r) =>
    (!skill || String(r.skill_id) === skill) && (!type || r.type === type) && (!difficulty || r.difficulty === difficulty) &&
    (!status || r.status === status) &&
    (!search.trim() || `${r.title} ${r.provider} ${r.skill}`.toLowerCase().includes(search.trim().toLowerCase()))),
  [data.resources, skill, type, difficulty, status, search]);

  async function save(r: Resource, next: ProgressStatus, notes?: string) {
    setBusy(true);
    try {
      await postJson(`/api/v1/progress/${r.id}`, { status: next, ...(notes !== undefined ? { notes } : {}) });
      await data.load();
      toast('success', notes !== undefined ? 'Notes saved.' : 'Learning progress updated.');
      setNoting(null);
    } catch (e) {
      toast('error', errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Learning resources <small className="muted">({shown.length} of {data.resources.length})</small></h2>
      <p className="muted">Free official documentation, courses and practice for every skill. Links were checked when the catalogue was built.</p>
      <div className="filters">
        <label className="search">
          <Search size={15} aria-hidden="true" />
          <input aria-label="Search resources" placeholder="Title or provider" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <select aria-label="Skill" value={skill} onChange={(e) => setSkill(e.target.value)}>
          <option value="">All skills</option>
          {data.skills.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select aria-label="Type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>{TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select aria-label="Difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="">All levels</option><option>beginner</option><option>intermediate</option><option>advanced</option>
        </select>
        {canTrack && (
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option><option value="not_started">Not started</option>
            <option value="in_progress">In progress</option><option value="completed">Completed</option>
          </select>
        )}
      </div>
      {!shown.length && <Empty text="No resources match these filters." />}
      <div className="resource-grid">
        {shown.map((r) => (
          <article className={`resource status-${r.status}`} key={r.id}>
            <div className="resource-top">
              <span>{r.skill}</span>
              <span className={`pill diff-${r.difficulty}`}>{r.difficulty}</span>
            </div>
            <h3>{r.title}</h3>
            <p>{r.description}</p>
            <small>{r.provider} · {r.type} · {r.is_free ? 'Free' : 'Paid'}{r.estimated_hours ? ` · ~${r.estimated_hours} h` : ''}</small>
            {canTrack ? (
              <>
                <ResourceActions r={r} onChange={(st) => save(r, st)} />
                <button className="link-button note-btn" onClick={() => setNoting(r)}><NotebookPen size={13} /> {r.notes ? 'Edit notes' : 'Add notes'}</button>
                {r.notes && <p className="resource-note">{r.notes}</p>}
              </>
            ) : (
              <div className="resource-actions"><a href={safeUrl(r.url)} target="_blank" rel="noreferrer noopener" className="link-button">Open ↗</a></div>
            )}
          </article>
        ))}
      </div>

      {noting && (
        <div className="dialog-backdrop" onClick={() => setNoting(null)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="note-title" onClick={(e) => e.stopPropagation()}>
            <h3 id="note-title">Notes: {noting.title}</h3>
            <textarea className="note-area" rows={6} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="What did you learn? What to revisit?" aria-label="Notes" />
            <small className="muted">{note.length}/2000</small>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setNoting(null)}>Cancel</button>
              <button className="primary" disabled={busy}
                onClick={() => save(noting, noting.status === 'not_started' ? 'in_progress' : noting.status, note)}>
                {busy && <Spinner />} Save notes
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
