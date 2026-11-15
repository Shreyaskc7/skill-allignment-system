import { useCallback, useState } from 'react';
import { errorMessage, postJson } from './api/client';
import { Sidebar } from './components/Sidebar';
import { useAppData } from './hooks/useAppData';
import { useAssessment } from './hooks/useAssessment';
import { AssessmentPage } from './pages/AssessmentPage';
import { FacultyInsightsPage } from './pages/FacultyInsightsPage';
import { JobMarketPage } from './pages/JobMarketPage';
import { LearningResourcesPage } from './pages/LearningResourcesPage';
import { OverviewPage } from './pages/OverviewPage';
import { ProgressPage } from './pages/ProgressPage';
import { SkillGapsPage } from './pages/SkillGapsPage';
import type { Page, ProgressStatus } from './types';
import './styles.css';

export default function App() {
  const [page, setPage] = useState<Page>('Overview');
  const [notice, setNoticeState] = useState('');
  const setNotice = useCallback((message: string) => setNoticeState(message), []);

  const data = useAppData(setNotice);
  const assessment = useAssessment(data.assessmentSkills, data.load, setNotice);

  async function markResource(id: number, status: ProgressStatus) {
    try {
      await postJson('/api/v1/progress/' + id, { status });
      await data.load();
      setNotice('Learning progress updated.');
    } catch (e) {
      setNotice(errorMessage(e));
    }
  }

  function navigate(next: Page) {
    setPage(next);
    setNotice('');
  }

  return (
    <div className="shell">
      <Sidebar page={page} online={data.online} onNavigate={navigate} onRefresh={data.load} />
      <main>
        <header>
          <div>
            <small>WORKSPACE / {page.toUpperCase()}</small>
            <h1>{page === 'Overview' ? 'Build skills. Unlock potential.' : page}</h1>
          </div>
          <div className="profile">
            <span className={data.online ? 'dot' : 'dot off'} /> Student Preview
          </div>
        </header>

        <div className="content">
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button aria-label="Dismiss" onClick={() => setNotice('')}>
                ×
              </button>
            </div>
          )}

          {page === 'Overview' && <OverviewPage data={data} onStartAssessment={() => setPage('Assessment')} />}
          {page === 'Assessment' && <AssessmentPage skills={data.assessmentSkills} a={assessment} />}
          {page === 'Skill Gaps' && <SkillGapsPage data={data} />}
          {page === 'Learning Resources' && (
            <LearningResourcesPage resources={data.resources} onStatusChange={markResource} />
          )}
          {page === 'Job Market' && <JobMarketPage jobs={data.jobs} reload={data.load} setNotice={setNotice} />}
          {page === 'Progress' && <ProgressPage progress={data.progress} />}
          {page === 'Faculty Insights' && <FacultyInsightsPage faculty={data.faculty} />}

          <footer>
            SkillAlign · Intelligent Workforce Skill Alignment System <span>Academic project prototype</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
