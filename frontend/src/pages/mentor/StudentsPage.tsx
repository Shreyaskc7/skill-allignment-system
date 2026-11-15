import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { errorMessage, request } from '../../api/client';
import { Empty } from '../../components/common';
import { Alert, LoadingScreen } from '../../components/ui';
import type { StudentSummary } from '../../types';

export function StudentsPage() {
  const [items, setItems] = useState<StudentSummary[] | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const t = setTimeout(() => {
      const q = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : '';
      request<StudentSummary[]>(`/api/v1/mentor/students${q}`).then(setItems).catch((e) => setError(errorMessage(e)));
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Students</h2>
        <label className="search">
          <Search size={15} aria-hidden="true" />
          <input aria-label="Search students" placeholder="Search name or email" value={search}
            onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>
      {error && <Alert>{error}</Alert>}
      {!items && !error && <LoadingScreen />}
      {items && !items.length && <Empty text={search ? 'No students match your search.' : 'No students are assigned to you yet.'} />}
      {items && items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Target career</th>
                <th>Alignment</th>
                <th>Assessments</th>
                <th>Learning</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/app/mentor/students/${s.id}`} className="table-link">{s.full_name}</Link>
                    <small className="cell-sub">{s.email}</small>
                  </td>
                  <td>{s.target_career?.name ?? <span className="muted">Not set</span>}</td>
                  <td>{s.target_career ? `${s.target_career.alignment_score}%` : '–'}</td>
                  <td>
                    {s.assessments.count}
                    {s.assessments.average_score != null && <small className="cell-sub">avg {s.assessments.average_score}%</small>}
                  </td>
                  <td>{s.learning.completed} done · {s.learning.in_progress} active</td>
                  <td>
                    {s.needs_attention.length ? (
                      <span className="pill high" title={s.needs_attention.join('\n')}>Needs attention</span>
                    ) : (
                      <span className="pill">On track</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
