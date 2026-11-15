import { useEffect, useState } from 'react';
import { errorMessage, postJson, request } from '../api/client';
import type { AssessmentResult, AssessmentSkill, Question } from '../types';

/**
 * Assessment state lives at app level so an in-progress quiz survives switching pages.
 * Phase 6 replaces this with server-side attempt records.
 */
export function useAssessment(
  assessmentSkills: AssessmentSkill[],
  reload: () => Promise<void>,
  setNotice: (message: string) => void,
) {
  const [selectedSkill, setSelectedSkill] = useState<number | ''>('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSelectedSkill((old) => old || assessmentSkills[0]?.id || '');
  }, [assessmentSkills]);

  function selectSkill(id: number) {
    setSelectedSkill(id);
    setQuestions([]);
    setResult(null);
  }

  async function start() {
    if (!selectedSkill) return;
    setBusy(true);
    try {
      setQuestions(await request<Question[]>(`/api/v1/assessments/questions/${selectedSkill}`));
      setAnswers({});
      setResult(null);
    } catch (e) {
      setNotice(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    try {
      setResult(await postJson<AssessmentResult>('/api/v1/assessments/submit', { skill_id: selectedSkill, answers }));
      await reload();
    } catch (e) {
      setNotice(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const answer = (questionId: number, option: string) =>
    setAnswers((a) => ({ ...a, [String(questionId)]: option }));

  return { selectedSkill, selectSkill, questions, answers, answer, result, busy, start, submit };
}

export type AssessmentState = ReturnType<typeof useAssessment>;
