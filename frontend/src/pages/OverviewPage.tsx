import { BookOpen, Briefcase, ClipboardList, Target } from 'lucide-react';
import { CareerSelect, Empty, Metric } from '../components/common';
import type { AppData } from '../hooks/useAppData';

export function OverviewPage({ data, onStartAssessment }: { data: AppData; onStartAssessment: () => void }) {
  const { gap, careers, role, setRole, dashboard, analytics } = data;
  const score = gap?.alignment_score ?? 0;
  const topDemand = analytics[0]?.postings || 1;
  return (
    <>
      <section className="hero">
        <div>
          <label>YOUR CAREER JOURNEY</label>
          <h2>
            Turn your skills into
            <br />
            <em>career readiness.</em>
          </h2>
          <p>Assess your abilities, discover skill gaps and follow a practical learning path.</p>
          <button className="primary" onClick={onStartAssessment}>
            Start assessment →
          </button>
        </div>
        <div className="hero-score">
          <span>CAREER ALIGNMENT</span>
          <strong>
            {score}
            <small>%</small>
          </strong>
          <div className="progress">
            <i style={{ width: `${score}%` }} />
          </div>
          <small>{gap?.career || 'Select a target role'}</small>
        </div>
      </section>

      <div className="toolbar">
        <CareerSelect careers={careers} role={role} onChange={setRole} />
      </div>

      <div className="metrics">
        <Metric icon={<Briefcase />} label="Job postings" value={dashboard?.job_count ?? 0} />
        <Metric icon={<Target />} label="Skills catalogued" value={dashboard?.skill_count ?? 0} />
        <Metric icon={<ClipboardList />} label="Assessments taken" value={dashboard?.assessment_count ?? 0} />
        <Metric icon={<BookOpen />} label="Learning resources" value={dashboard?.resource_count ?? 0} />
      </div>

      <div className="grid2">
        <section className="panel">
          <h3>Priority skill gaps</h3>
          <p className="muted">Based on assessments and your selected career.</p>
          {(gap?.skills || []).slice(0, 7).map((x) => (
            <div className="gaprow" key={x.skill}>
              <div>
                <b>{x.skill}</b>
                <small>
                  Current {x.current_level || 'Not assessed'} / 5 · Target {x.required_level}/5
                </small>
              </div>
              <span className={'pill ' + (x.priority === 'High' ? 'high' : '')}>{x.priority}</span>
            </div>
          ))}
          {!gap?.skills?.length && <Empty text="Choose a career role to view required skills." />}
        </section>

        <section className="panel">
          <h3>Most requested skills</h3>
          <p className="muted">Extracted from imported job postings.</p>
          {analytics.slice(0, 7).map((x) => (
            <div className="barrow" key={x.skill}>
              <span>{x.skill}</span>
              <div className="bar">
                <i style={{ width: `${Math.max(5, (x.postings / topDemand) * 100)}%` }} />
              </div>
              <b>{x.postings}</b>
            </div>
          ))}
          {!analytics.length && <Empty text="Import job-posting CSV files to see demand analytics." />}
        </section>
      </div>
    </>
  );
}
