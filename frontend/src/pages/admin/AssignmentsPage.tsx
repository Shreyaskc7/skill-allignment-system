import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { errorMessage, postJson, request } from '../../api/client';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen, Spinner, useToast } from '../../components/ui';
import type { AdminUser, Assignment } from '../../types';

export function AssignmentsPage() {
  const toast = useToast();
  const [students, setStudents] = useState<AdminUser[]>([]);
  const [teachers, setTeachers] = useState<AdminUser[]>([]);
  const [items, setItems] = useState<Assignment[] | null>(null);
  const [error, setError] = useState('');
  const [studentId, setStudentId] = useState('');
  const [teacherId, setTeacherId] = useState('');
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [ending, setEnding] = useState<Assignment | null>(null);
  const [reason, setReason] = useState('');

  const load = useCallback(() => {
    Promise.all([
      request<AdminUser[]>('/api/v1/admin/users?role=student'),
      request<AdminUser[]>('/api/v1/admin/users?role=teacher'),
      request<Assignment[]>('/api/v1/admin/assignments'),
    ])
      .then(([s, t, a]) => {
        setStudents(s.filter((u) => u.is_active));
        setTeachers(t.filter((u) => u.is_active));
        setItems(a);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  async function assign(e: FormEvent) {
    e.preventDefault();
    if (!studentId || !teacherId) return toast('error', 'Choose both a student and a mentor.');
    setBusy(true);
    try {
      await postJson('/api/v1/admin/assignments', { student_id: Number(studentId), teacher_id: Number(teacherId) });
      toast('success', 'Student assigned.');
      setStudentId('');
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function end() {
    if (!ending) return;
    if (reason.trim().length < 3) return toast('error', 'Give a short reason (at least 3 characters).');
    try {
      await postJson(`/api/v1/admin/assignments/${ending.id}/end`, { reason: reason.trim() });
      toast('success', `${ending.student_name} is no longer assigned to ${ending.teacher_name}.`);
      setEnding(null);
      setReason('');
      load();
    } catch (err) {
      toast('error', errorMessage(err));
    }
  }

  if (error) return <Alert>{error}</Alert>;
  if (!items) return <LoadingScreen />;
  const shown = items.filter((a) => showHistory || a.is_active);

  return (
    <>
      <section className="panel">
        <h2>Assign a student to a mentor</h2>
        <p className="muted">Mentors can view and support only the students actively assigned to them.</p>
        <form className="inline-form" onSubmit={assign}>
          <div className="field">
            <label htmlFor="as-student">Student</label>
            <select id="as-student" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
              <option value="">Choose a student…</option>
              {students.map((s) => <option key={s.id} value={s.id}>{s.full_name} ({s.email})</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="as-teacher">Mentor</label>
            <select id="as-teacher" value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
              <option value="">Choose a mentor…</option>
              {teachers.map((t) => <option key={t.id} value={t.id}>{t.full_name} ({t.email})</option>)}
            </select>
          </div>
          <button className="primary" type="submit" disabled={busy}>{busy && <Spinner />} Assign</button>
        </form>
        {!teachers.length && <Alert kind="info">No mentors yet. Invite one from Mentor Invitations.</Alert>}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>{showHistory ? 'All assignments (history)' : 'Active assignments'}</h2>
          <label className="checkbox inline">
            <input type="checkbox" checked={showHistory} onChange={(e) => setShowHistory(e.target.checked)} />
            <span>Show ended assignments</span>
          </label>
        </div>
        {!shown.length && <Empty text="No assignments yet." />}
        {shown.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Student</th><th>Mentor</th><th>Assigned</th><th>Status</th><th aria-label="Actions" /></tr>
              </thead>
              <tbody>
                {shown.map((a) => (
                  <tr key={a.id}>
                    <td>{a.student_name}<small className="cell-sub">{a.student_email}</small></td>
                    <td>{a.teacher_name}</td>
                    <td>{new Date(a.assigned_at).toLocaleDateString()}{a.assigned_by && <small className="cell-sub">by {a.assigned_by}</small>}</td>
                    <td>
                      {a.is_active ? <span className="pill">active</span> : (
                        <>
                          <span className="pill status-revoked">ended</span>
                          <small className="cell-sub">{a.removed_at && new Date(a.removed_at).toLocaleDateString()}: {a.removal_reason}</small>
                        </>
                      )}
                    </td>
                    <td>{a.is_active && <button className="link-button danger" onClick={() => setEnding(a)}>End</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {ending && (
        <div className="dialog-backdrop" onClick={() => setEnding(null)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="end-title" onClick={(e) => e.stopPropagation()}>
            <h3 id="end-title">End this assignment?</h3>
            <div className="dialog-body">
              {ending.teacher_name} will lose access to {ending.student_name}’s records. The assignment stays in the history.
              <div className="field" style={{ marginTop: 12 }}>
                <label htmlFor="end-reason">Reason</label>
                <input id="end-reason" autoFocus value={reason} onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Reassigned to another department" />
              </div>
            </div>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setEnding(null)}>Cancel</button>
              <button className="primary danger" onClick={end}>End assignment</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
