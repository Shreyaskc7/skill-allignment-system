import type { AssessmentSkill } from '../types';
import type { AssessmentState } from '../hooks/useAssessment';

export function AssessmentPage({ skills, a }: { skills: AssessmentSkill[]; a: AssessmentState }) {
  const allAnswered = Object.keys(a.answers).length === a.questions.length;
  return (
    <section className="panel">
      <h2>Skill assessment</h2>
      <p className="muted">
        Answer the multiple-choice questions. Your result updates your skill profile and career alignment.
      </p>

      <div className="toolbar">
        <label>Select skill</label>
        <select value={a.selectedSkill} onChange={(e) => a.selectSkill(Number(e.target.value))}>
          {skills.map((s) => (
            <option value={s.id} key={s.id}>
              {s.name} ({s.question_count} questions)
            </option>
          ))}
        </select>
        <button className="primary" onClick={a.start} disabled={a.busy}>
          Load questions
        </button>
      </div>

      {a.questions.map((q, i) => (
        <div className="question" key={q.id}>
          <b>
            {i + 1}. {q.question}
          </b>
          {Object.entries(q.options).map(([k, v]) => (
            <label className="option" key={k}>
              <input
                type="radio"
                name={'q' + q.id}
                checked={a.answers[String(q.id)] === k}
                onChange={() => a.answer(q.id, k)}
              />
              <span>
                {k}. {v}
              </span>
            </label>
          ))}
        </div>
      ))}

      {a.questions.length > 0 && (
        <button className="primary" disabled={a.busy || !allAnswered} onClick={a.submit}>
          Submit assessment
        </button>
      )}

      {a.result && (
        <div className="result">
          <h3>Assessment result: {a.result.score_percent}%</h3>
          <p>
            {a.result.correct} correct out of {a.result.total}. Estimated proficiency level:{' '}
            {a.result.estimated_level}/5.
          </p>
          {a.result.review.map((r, i) => (
            <div className="review" key={r.question_id}>
              <b>
                Question {i + 1}: {r.is_correct ? 'Correct' : 'Review this answer'}
              </b>
              <p>
                Your answer: {r.your_answer || 'Not answered'} · Correct: {r.correct_option}
              </p>
              <small>{r.explanation}</small>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
