import { Navigate, Route, Routes } from 'react-router-dom';
import { homeFor, useAuth } from './auth/AuthContext';
import { AnonymousOnly, RequireAuth, RequireRole } from './auth/guards';
import { AppLayout, useApp } from './components/AppLayout';
import { InvitationsPage } from './pages/admin/InvitationsPage';
import { AssessmentPage } from './pages/assessment/AssessmentPage';
import { ResultsPage } from './pages/assessment/ResultsPage';
import { QuestionBankPage } from './pages/mentor/QuestionBankPage';
import { AcceptInvitationPage } from './pages/auth/AcceptInvitationPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';
import { FacultyInsightsPage } from './pages/FacultyInsightsPage';
import { JobMarketPage } from './pages/jobs/JobMarketPage';
import { JobDetailPage } from './pages/jobs/JobDetailPage';
import { LandingPage } from './pages/LandingPage';
import { LearningResourcesPage } from './pages/LearningResourcesPage';
import { StudentDashboardPage } from './pages/StudentDashboardPage';
import { ProfilePage } from './pages/ProfilePage';
import { AccountPage } from './pages/AccountPage';
import { CareersPage } from './pages/CareersPage';
import { LearningPathPage } from './pages/learning/LearningPathPage';
import { AssignmentsPage } from './pages/admin/AssignmentsPage';
import { MentorDashboardPage } from './pages/mentor/MentorDashboardPage';
import { StudentDetailPage } from './pages/mentor/StudentDetailPage';
import { StudentsPage } from './pages/mentor/StudentsPage';
import { TeacherProfilePage } from './pages/mentor/TeacherProfilePage';
import { ProgressPage } from './pages/ProgressPage';
import { SkillGapsPage } from './pages/SkillGapsPage';

// --- thin route adapters: read shared data from the layout and pass it to the page components

function Resources() {
  const { user } = useAuth();
  return <LearningResourcesPage canTrack={user!.role === 'student'} />;
}

function RootRedirect() {
  const { status, user } = useAuth();
  if (status === 'authenticated') return <Navigate to={homeFor(user)} replace />;
  return <LandingPage />;
}

function AppHome() {
  const { user } = useAuth();
  return user!.role === 'student' ? <StudentDashboardPage /> : <Navigate to={homeFor(user)} replace />;
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
          <Route path="jobs" element={<JobMarketPage />} />
          <Route path="jobs/:id" element={<JobDetailPage />} />
          <Route path="account" element={<AccountPage />} />
          <Route element={<RequireRole roles={['student']} />}>
            <Route path="assessment" element={<AssessmentPage />} />
            <Route path="assessment/results/:id" element={<ResultsPage />} />
            <Route path="skill-gaps" element={<SkillGapsRoute />} />
            <Route path="careers" element={<CareersPage />} />
            <Route path="learning-path" element={<LearningPathPage />} />
            <Route path="progress" element={<ProgressRoute />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
          <Route element={<RequireRole roles={['teacher', 'admin']} />}>
            <Route path="faculty" element={<FacultyRoute />} />
            <Route path="mentor" element={<MentorDashboardPage />} />
            <Route path="mentor/students" element={<StudentsPage />} />
            <Route path="mentor/students/:id" element={<StudentDetailPage />} />
            <Route path="question-bank" element={<QuestionBankPage />} />
          </Route>
          <Route element={<RequireRole roles={['teacher']} />}>
            <Route path="teacher-profile" element={<TeacherProfilePage />} />
          </Route>
          <Route element={<RequireRole roles={['admin']} />}>
            <Route path="admin/invitations" element={<InvitationsPage />} />
            <Route path="admin/assignments" element={<AssignmentsPage />} />
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
