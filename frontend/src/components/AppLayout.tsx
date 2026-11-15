import { useCallback, useState } from 'react';
import { Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useAppData, type AppData } from '../hooks/useAppData';
import { useAssessment, type AssessmentState } from '../hooks/useAssessment';
import { ConfirmDialog, LoadingScreen, useToast } from './ui';
import { ErrorBoundary } from './ErrorBoundary';
import { NAV, Sidebar } from './Sidebar';

export type AppContext = { data: AppData; assessment: AssessmentState };
export const useApp = () => useOutletContext<AppContext>();

export function AppLayout() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [confirmLogout, setConfirmLogout] = useState(false);
  const onError = useCallback((m: string) => toast('error', m), [toast]);

  const data = useAppData(user!.role, onError);
  const assessment = useAssessment(data.assessmentSkills, data.load, onError);

  const current = [...NAV].reverse().find((n) => location.pathname.startsWith(n.to));
  const title = current?.to === '/app' ? 'Build skills. Unlock potential.' : current?.label ?? 'SkillAlign';

  async function signOut() {
    setConfirmLogout(false);
    await logout();
    navigate('/login', { replace: true, state: { notice: 'You have signed out.' } });
  }

  return (
    <div className="shell">
      <Sidebar user={user!} online={data.online} onRefresh={data.load} onLogout={() => setConfirmLogout(true)} />
      <main>
        <header>
          <div>
            <small>WORKSPACE / {(current?.label ?? '').toUpperCase()}</small>
            <h1>{title}</h1>
          </div>
          <div className="profile">
            <span className={data.online ? 'dot' : 'dot off'} /> {user!.full_name}
            <button className="icon-button" aria-label="Sign out" onClick={() => setConfirmLogout(true)}>
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <div className="content">
          <ErrorBoundary resetKey={location.pathname}>
            {data.loaded ? <Outlet context={{ data, assessment } satisfies AppContext} /> : <LoadingScreen />}
          </ErrorBoundary>
          <footer>
            SkillAlign · Intelligent Workforce Skill Alignment System <span>Academic project prototype</span>
          </footer>
        </div>
      </main>
      {confirmLogout && (
        <ConfirmDialog title="Sign out?" confirmLabel="Sign out" onCancel={() => setConfirmLogout(false)}
          onConfirm={signOut}>
          You will need to sign in again to continue.
        </ConfirmDialog>
      )}
    </div>
  );
}
