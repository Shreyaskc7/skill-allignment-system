import { Navigate, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import type { Role } from '../types';
import { homeFor, useAuth } from './AuthContext';
import { LoadingScreen } from '../components/ui';

/** Only for signed-in users; remembers where the user was going. */
export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <LoadingScreen />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

/** Client-side convenience only: the backend enforces every permission independently. */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  // Nested outlets do not inherit context automatically: forward the layout's shared data.
  const context = useOutletContext();
  if (!user || !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return <Outlet context={context} />;
}

/** Pages like login/register redirect signed-in users to their dashboard. */
export function AnonymousOnly() {
  const { status, user } = useAuth();
  if (status === 'loading') return <LoadingScreen />;
  if (status === 'authenticated') return <Navigate to={homeFor(user)} replace />;
  return <Outlet />;
}
