import { CareerSelect } from '../components/common';
import type { AppData } from '../hooks/useAppData';

export function SkillGapsPage({ data }: { data: AppData }) {
  const { careers, role, setRole, gap } = data;
  return (
    <>
      <div className="toolbar">
        <CareerSelect careers={careers} role={role} onChange={setRole} />
        <div className="scorechip">Alignment {gap?.alignment_score ?? 0}%</div>
      </div>
      <section className="panel">
        <h2>{gap?.career || 'Skill gap analysis'}</h2>
        <p className="muted">
          Weighted alignment = assessed proficiency capped at required level, divided by total role importance
          weights.
        </p>
        {(gap?.skills || []).map((x) => (
          <div className="gapdetail" key={x.skill}>
            <div>
              <b>{x.skill}</b>
              <small>
                {x.priority} priority · Weight {x.importance}
              </small>
            </div>
            <div className="levelbars">
              <span>Current {x.current_level}/5</span>
              <span>Required {x.required_level}/5</span>
              <div className="progress">
                <i style={{ width: `${(x.current_level / 5) * 100}%` }} />
              </div>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
