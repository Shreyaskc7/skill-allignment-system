import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { errorMessage, postJson } from './api/client';
import { homeFor, useAuth } from './auth/AuthContext';
import { AnonymousOnly, RequireAuth, RequireRole } from './auth/guards';
import { AppLayout, useApp } from './components/AppLayout';
import { useToast } from './components/ui';
import { InvitationsPage } from './pages/admin/InvitationsPage';
import { AssessmentPage } from './pages/AssessmentPage';
import { AcceptInvitationPage } from './pages/auth/AcceptInvitationPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';
import { FacultyInsightsPage } from './pages/FacultyInsightsPage';
import { JobMarketPage } from './pages/JobMarketPage';
import { LandingPage } from './pages/LandingPage';
import { LearningResourcesPage } from './pages/LearningResourcesPage';
import { OverviewPage } from './pages/OverviewPage';
import { ProgressPage } from './pages/ProgressPage';
import { SkillGapsPage } from './pages/SkillGapsPage';
import type { ProgressStatus } from './types';

// --- thin route adapters: read shared data from the layout and pass it to the page components

function Overview() {
  const { data } = useApp();
  const navigate = useNavigate();
  return <OverviewPage data={data} onStartAssessment={() => navigate('/app/assessment')} />;
}

function Assessment() {
  const { data, assessment } = useApp();
  return <AssessmentPage skills={data.assessmentSkills} a={assessment} />;
}

function Resources() {
  const { data } = useApp();
  const { user } = useAuth();
  const toast = useToast();
  async function mark(id: number, status: ProgressStatus) {
    try {
      await postJson('/api/v1/progress/' + id, { status });
      await data.load();
      toast('success', 'Learning progress updated.');
    } catch (e) {
      toast('error', errorMessage(e));
    }
  }
  return (
    <LearningResourcesPage resources={data.resources} onStatusChange={mark} canTrack={user!.role === 'student'} />
  );
}

function Jobs() {
  const { data } = useApp();
  const { user } = useAuth();
  const toast = useToast();
  return (
    <JobMarketPage
      jobs={data.jobs}
      reload={data.load}
      canImport={user!.role !== 'student'}
      notify={(kind, message) => toast(kind, message)}
    />
  );
}

function RootRedirect() {
  const { status, user } = useAuth();
  if (status === 'authenticated') return <Navigate to={homeFor(user)} replace />;
  return <LandingPage />;
}

function AppHome() {
  const { user } = useAuth();
  return user!.role === 'student' ? <Overview /> : <Navigate to={homeFor(user)} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route element={<AnonymousOnly />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      </Route>
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/accept-invitation" element={<AcceptInvitationPage />} />

      <Route element={<RequireAuth />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<AppHome />} />
          <Route path="resources" element={<Resources />} />
          <Route path="jobs" element={<Jobs />} />
          <Route element={<RequireRole roles={['student']} />}>
            <Route path="assessment" element={<Assessment />} />
            <Route path="skill-gaps" element={<SkillGapsRoute />} />
            <Route path="progress" element={<ProgressRoute />} />
          </Route>
          <Route element={<RequireRole roles={['teacher', 'admin']} />}>
            <Route path="faculty" element={<FacultyRoute />} />
          </Route>
          <Route element={<RequireRole roles={['admin']} />}>
            <Route path="admin/invitations" element={<InvitationsPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function SkillGapsRoute() {
  return <SkillGapsPage data={useApp().data} />;
}
function ProgressRoute() {
  return <ProgressPage progress={useApp().data.progress} />;
}
function FacultyRoute() {
  return <FacultyInsightsPage faculty={useApp().data.faculty} />;
}
