import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { safeUrl } from '../../api/safeUrl';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, EyeOff, Trash2 } from 'lucide-react';
import { errorMessage, postJson, request } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { useApp } from '../../components/AppLayout';
import { Empty } from '../../components/common';
import { Alert, ConfirmDialog, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { MentoringNote, NoteType, StudentDetail } from '../../types';

const NOTE_LABEL: Record<NoteType, string> = {
  general: 'General', feedback: 'Feedback', resource_recommendation: 'Resource recommendation', concern: 'Concern (private)',
};

export function StudentDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data } = useApp();
  const toast = useToast();
  const [d, setD] = useState<StudentDetail | null>(null);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [type, setType] = useState<NoteType>('feedback');
  const [resourceId, setResourceId] = useState('');
  const [shared, setShared] = useState(true);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<MentoringNote | null>(null);

  const load = useCallback(() => {
    request<StudentDetail>(`/api/v1/mentor/students/${id}`).then(setD).catch((e) => setError(errorMessage(e)));
  }, [id]);
  useEffect(load, [load]);

  async function addNote(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return toast('error', 'Write a note first.');
    if (type === 'resource_recommendation' && !resourceId) return toast('error', 'Choose the resource you recommend.');
    setBusy(true);
    try {
      await postJson(`/api/v1/mentor/students/${id}/notes`, {
        note, note_type: type, resource_id: resourceId ? Number(resourceId) : null, visible_to_student: shared,
      });
      setNote('');
      setResourceId('');
      toast('success', 'Note saved.');
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteNote(n: MentoringNote) {
    setDeleting(null);
    try {
      await request(`/api/v1/mentor/notes/${n.id}`, { method: 'DELETE' });
      toast('success', 'Note deleted.');
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  if (error) return <Alert>{error}</Alert>;
  if (!d) return <LoadingScreen />;
  const s = d.summary;

  return (
    <>
      <Link to="/app/mentor/students" className="more-link back"><ArrowLeft size={14} /> All students</Link>
      <section className="panel">
        <h2>{s.full_name}</h2>
        <p className="muted">
          {s.email}
          {d.profile?.college && <> · {d.profile.college}</>}
          {d.profile?.degree && <> · {d.profile.degree}</>}
          {d.profile?.current_semester && <> · Semester {d.profile.current_semester}</>}
        </p>
        {s.needs_attention.length > 0 && <Alert kind="info">Needs attention: {s.needs_attention.join(' · ')}</Alert>}
        <div className="detail-grid">
          <div><small>Target career</small><b>{s.target_career?.name ?? 'Not set'}</b></div>
          <div><small>Alignment</small><b>{s.target_career ? `${s.target_career.alignment_score}%` : '–'}</b></div>
          <div><small>Assessments</small><b>{s.assessments.count}{s.assessments.average_score != null && ` (avg ${s.assessments.average_score}%)`}</b></div>
          <div><small>Learning</small><b>{s.learning.completed} completed · {s.learning.in_progress} in progress</b></div>
        </div>
        {d.profile?.career_interests && <p className="small"><b>Interests:</b> {d.profile.career_interests}</p>}
      </section>

      <div className="grid2">
        <section className="panel">
          <h3>Skill gaps{d.gaps ? ` · ${d.gaps.career}` : ''}</h3>
          {d.gaps ? d.gaps.skills.map((g) => (
            <div className="gaprow" key={g.skill_id}>
              <div><b>{g.skill}</b><small>Current {g.current_level}/5 · Required {g.required_level}/5 · Weight {g.importance}</small></div>
              <span className={'pill ' + (g.priority === 'High' ? 'high' : '')}>{g.priority}</span>
            </div>
          )) : <Empty text="The student has not selected a target career." />}
        </section>

        <section className="panel">
          <h3>Performance by skill</h3>
          <p className="muted">Topic-level breakdown becomes available with the new assessment engine.</p>
          {d.skill_performance.map((p) => (
            <div className="gaprow" key={p.skill}>
              <div><b>{p.skill}</b><small>{p.attempts} attempt(s) · best {p.best}% · average {p.average}%</small></div>
              <span className="scorechip">{p.latest}%</span>
            </div>
          ))}
          {!d.skill_performance.length && <Empty text="No assessments yet." />}
        </section>

        <section className="panel">
          <h3>Assessment history</h3>
          {d.assessments.map((a) => (
            <div className="gaprow" key={a.id}>
              <div><b>{a.skill}</b><small>{new Date(a.created_at).toLocaleString()} · {a.correct}/{a.total} correct</small></div>
              <span className="scorechip">{a.score_percent}%</span>
            </div>
          ))}
          {!d.assessments.length && <Empty text="No assessments yet." />}
        </section>

        <section className="panel">
          <h3>Learning progress</h3>
          {d.learning.map((l, i) => (
            <div className="gaprow" key={i}>
              <div><b>{l.resource}</b><small>{l.skill} · updated {new Date(l.updated_at).toLocaleDateString()}</small></div>
              <span className="pill">{l.status.replace('_', ' ')}</span>
            </div>
          ))}
          {!d.learning.length && <Empty text="Not tracking any resources yet." />}
          {d.self_reported_skills.length > 0 && (
            <p className="small muted">Self-reported (unverified): {d.self_reported_skills.map((x) => `${x.skill} ${x.level}/5`).join(', ')}</p>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Mentoring notes</h3>
        <form className="note-form" onSubmit={addNote} noValidate>
          <div className="note-options">
            <select aria-label="Note type" value={type} onChange={(e) => setType(e.target.value as NoteType)}>
              {(Object.keys(NOTE_LABEL) as NoteType[]).map((k) => <option key={k} value={k}>{NOTE_LABEL[k]}</option>)}
            </select>
            {(type === 'resource_recommendation' || type === 'feedback') && (
              <select aria-label="Recommended resource" value={resourceId} onChange={(e) => setResourceId(e.target.value)}>
                <option value="">{type === 'resource_recommendation' ? 'Choose a resource…' : 'Attach a resource (optional)'}</option>
                {data.resources.map((r) => <option key={r.id} value={r.id}>{r.skill}: {r.title}</option>)}
              </select>
            )}
            {type !== 'concern' && (
              <label className="checkbox inline">
                <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
                <span>Visible to the student</span>
              </label>
            )}
          </div>
          <textarea aria-label="Note" rows={3} maxLength={4000} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={type === 'concern' ? 'Private note for staff only' : 'Write feedback or guidance for the student'} />
          <button className="primary" type="submit" disabled={busy}>{busy && <Spinner />} Add note</button>
        </form>
        {d.notes.map((n) => (
          <div className="note" key={n.id}>
            <div className="note-meta">
              <b>{n.teacher_name}</b> · {NOTE_LABEL[n.note_type]} · {new Date(n.created_at).toLocaleString()}
              {!n.visible_to_student && <span className="pill private"><EyeOff size={11} /> staff only</span>}
              {(n.teacher_id === user?.id || user?.role === 'admin') && (
                <button className="icon-button" aria-label="Delete note" onClick={() => setDeleting(n)}><Trash2 size={14} /></button>
              )}
            </div>
            <p>{n.note}</p>
            {n.resource && <a href={safeUrl(n.resource.url)} target="_blank" rel="noreferrer noopener" className="link-button">{n.resource.title} ↗</a>}
          </div>
        ))}
        {!d.notes.length && <Empty text="No notes yet." />}
      </section>

      {deleting && (
        <ConfirmDialog title="Delete note?" confirmLabel="Delete" onCancel={() => setDeleting(null)} onConfirm={() => deleteNote(deleting)}>
          This note will be removed permanently.
        </ConfirmDialog>
      )}
    </>
  );
}
