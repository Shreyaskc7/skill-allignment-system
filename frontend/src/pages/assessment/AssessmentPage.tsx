import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Clock, Flag, PlayCircle } from 'lucide-react';
import { errorMessage, postJson } from '../../api/client';
import { useApp } from '../../components/AppLayout';
import { Alert, ConfirmDialog, Spinner, useToast } from '../../components/ui';
import type { AttemptDelivery, AttemptResult } from '../../types';

type Answers = Record<number, string>;
const storeKey = (attemptId: number) => `skillalign.attempt.${attemptId}`;

function loadAnswers(attemptId: number): Answers {
  try {
    return JSON.parse(sessionStorage.getItem(storeKey(attemptId)) || '{}');
  } catch {
    return {};
  }
}

function saveAnswers(attemptId: number, answers: Answers) {
  try {
    sessionStorage.setItem(storeKey(attemptId), JSON.stringify(answers));
  } catch {
    /* storage unavailable: answers stay in memory only */
  }
}

function formatSeconds(s: number) {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

export function AssessmentPage() {
  const { data } = useApp();
  const navigate = useNavigate();
  const toast = useToast();
  const skills = data.assessmentSkills;
  const [skillId, setSkillId] = useState<number | ''>('');
  const [count, setCount] = useState(10);
  const [difficulty, setDifficulty] = useState('mixed');
  const [timed, setTimed] = useState(false);
  const [attempt, setAttempt] = useState<AttemptDelivery | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const clockOffset = useRef(0);
  const submitting = useRef(false);

  useEffect(() => {
    setSkillId((old) => old || skills[0]?.id || '');
  }, [skills]);

  const skill = skills.find((s) => s.id === skillId);
  const available = skill ? (difficulty === 'mixed' ? skill.question_count : skill.by_difficulty[difficulty as 'beginner']) : 0;

  async function start(restart = false) {
    if (!skillId) return;
    setBusy(true);
    try {
      const a = await postJson<AttemptDelivery>('/api/v1/assessments/attempts', {
        skill_id: skillId, question_count: count, difficulty, timed, restart,
      });
      clockOffset.current = new Date(a.server_time).getTime() - Date.now();
      setAttempt(a);
      setAnswers(loadAnswers(a.attempt_id));
      setIndex(0);
      if (a.resumed) toast('info', 'Resumed your unfinished attempt for this skill.');
    } catch (e) {
      toast('error', errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const submit = useCallback(async () => {
    if (!attempt || submitting.current) return;
    submitting.current = true;
    setConfirm(false);
    setBusy(true);
    try {
      const r = await postJson<AttemptResult>(`/api/v1/assessments/attempts/${attempt.attempt_id}/submit`, {
        answers: Object.entries(answers).map(([qid, answer]) => ({ question_id: Number(qid), answer })),
      });
      try { sessionStorage.removeItem(storeKey(attempt.attempt_id)); } catch { /* ignore */ }
      await data.load();
      navigate(`/app/assessment/results/${r.attempt_id}`);
    } catch (e) {
      toast('error', errorMessage(e));
      submitting.current = false;
      setBusy(false);
    }
  }, [attempt, answers, data, navigate, toast]);

  // Countdown for timed attempts (server time is authoritative; the server also enforces the limit).
  useEffect(() => {
    if (!attempt?.expires_at) return setRemaining(null);
    const end = new Date(attempt.expires_at).getTime();
    const tick = () => {
      const left = Math.max(0, Math.round((end - (Date.now() + clockOffset.current)) / 1000));
      setRemaining(left);
      if (left === 0) submit();
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [attempt, submit]);

  function choose(questionId: number, option: string) {
    if (!attempt) return;
    const next = { ...answers, [questionId]: option };
    setAnswers(next);
    saveAnswers(attempt.attempt_id, next);
  }

  const answered = useMemo(() => Object.keys(answers).length, [answers]);

  // ------------------------------------------------------------- setup screen
  if (!attempt) {
    return (
      <section className="panel narrow-wide">
        <h2>Skill assessment</h2>
        <p className="muted">Questions are drawn at random from the question bank for the skill you choose.</p>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="as-skill">Skill</label>
            <select id="as-skill" value={skillId} onChange={(e) => setSkillId(Number(e.target.value))}>
              {skills.map((s) => (
                <option key={s.id} value={s.id}>{s.name} ({s.question_count} questions)</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="as-diff">Difficulty</label>
            <select id="as-diff" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="mixed">Mixed (balanced)</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="as-count">Number of questions</label>
            <select id="as-count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <label className="checkbox inline timer-toggle">
            <input type="checkbox" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
            <span>Timed ({Math.round((count * 90) / 60)} minutes, 90 s per question)</span>
          </label>
        </div>
        {skill && available < count && (
          <Alert kind="info">Only {available} {difficulty === 'mixed' ? '' : difficulty} questions are available; you will get {available}.</Alert>
        )}
        <div className="instructions">
          <h3>Before you start</h3>
          <ul>
            <li>Each question has one correct answer. Unanswered questions count as incorrect.</li>
            <li>You can move between questions and change answers until you submit.</li>
            <li>Answers are saved in this browser tab, so a page reload does not lose them.</li>
            <li>Correct answers and explanations are shown only after you submit.</li>
            <li>Your score sets your proficiency level for the skill: 0–19% → 1, 20–39% → 2, 40–59% → 3, 60–79% → 4, 80–100% → 5.</li>
          </ul>
        </div>
        <button className="primary" onClick={() => start(false)} disabled={busy || !skillId || available < 5}>
          {busy ? <Spinner /> : <PlayCircle size={16} />} Start assessment
        </button>
      </section>
    );
  }

  // ------------------------------------------------------------- runner
  const q = attempt.questions[index];
  const last = index === attempt.questions.length - 1;
  const unanswered = attempt.questions.length - answered;

  return (
    <div className="runner">
      <section className="panel">
        <div className="runner-head">
          <div>
            <small className="muted">{attempt.skill} · question {index + 1} of {attempt.questions.length}</small>
            <div className="progress"><i style={{ width: `${(answered / attempt.questions.length) * 100}%` }} /></div>
            <small className="muted">{answered} answered</small>
          </div>
          {remaining != null && (
            <span className={'timer' + (remaining < 60 ? ' urgent' : '')} role="timer" aria-live="off">
              <Clock size={15} /> {formatSeconds(remaining)}
            </span>
          )}
        </div>

        <fieldset className="question-card" key={q.id}>
          <legend>
            <span className={`pill diff-${q.difficulty}`}>{q.difficulty}</span>
            <span className="q-text">{q.question}</span>
          </legend>
          {(Object.entries(q.options) as [string, string][]).map(([k, v]) => (
            <label className={'choice' + (answers[q.id] === k ? ' selected' : '')} key={k}>
              <input type="radio" name={`q${q.id}`} checked={answers[q.id] === k} onChange={() => choose(q.id, k)} />
              <b>{k}</b>
              <span className="q-text">{v}</span>
            </label>
          ))}
        </fieldset>

        <div className="runner-nav">
          <button className="secondary" onClick={() => setIndex((i) => i - 1)} disabled={index === 0}>
            <ChevronLeft size={16} /> Previous
          </button>
          {last ? (
            <button className="primary" onClick={() => setConfirm(true)} disabled={busy}>
              {busy ? <Spinner /> : <Flag size={16} />} Submit
            </button>
          ) : (
            <button className="primary" onClick={() => setIndex((i) => i + 1)}>
              Next <ChevronRight size={16} />
            </button>
          )}
        </div>
      </section>

      <aside className="panel question-nav" aria-label="Question navigation">
        <h3>Questions</h3>
        <div className="qgrid">
          {attempt.questions.map((x, i) => (
            <button key={x.id} className={(answers[x.id] ? 'done' : '') + (i === index ? ' current' : '')}
              onClick={() => setIndex(i)} aria-label={`Question ${i + 1}${answers[x.id] ? ', answered' : ', not answered'}`}>
              {i + 1}
            </button>
          ))}
        </div>
        <small className="muted legend"><i className="done" /> answered <i /> not answered</small>
        <button className="primary block" onClick={() => setConfirm(true)} disabled={busy}>Submit assessment</button>
        <button className="link-button" onClick={() => start(true)} disabled={busy}>Start over with new questions</button>
      </aside>

      {confirm && (
        <ConfirmDialog title="Submit assessment?" confirmLabel="Submit" onCancel={() => setConfirm(false)} onConfirm={submit}>
          {unanswered > 0
            ? <>You have <b>{unanswered} unanswered</b> question(s); they will count as incorrect.</>
            : 'All questions are answered.'} You cannot change answers after submitting.
        </ConfirmDialog>
      )}
    </div>
  );
}
