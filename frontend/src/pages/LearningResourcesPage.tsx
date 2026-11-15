import type { ProgressStatus, Resource } from '../types';

export function LearningResourcesPage({
  resources,
  onStatusChange,
  canTrack,
}: {
  resources: Resource[];
  onStatusChange: (id: number, status: ProgressStatus) => void;
  canTrack: boolean;
}) {
  return (
    <section className="panel">
      <h2>Learning resources</h2>
      <p className="muted">
        Curated free documentation, courses and practice material. Open a resource to study, then track your
        progress.
      </p>
      <div className="resource-grid">
        {resources.map((r) => (
          <article className="resource" key={r.id}>
            <div className="resource-top">
              <span>{r.skill}</span>
              <span className="pill">{r.difficulty}</span>
            </div>
            <h3>{r.title}</h3>
            <p>{r.description}</p>
            <small>
              {r.provider} · {r.type} · {r.is_free ? 'Free' : 'Paid'}
            </small>
            <div className="resource-actions">
              <a href={r.url} target="_blank" rel="noreferrer">
                Open resource ↗
              </a>
              {canTrack && (
              <select
                aria-label={`Progress for ${r.title}`}
                value={r.status}
                onChange={(e) => onStatusChange(r.id, e.target.value as ProgressStatus)}
              >
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
              </select>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
