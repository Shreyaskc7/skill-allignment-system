import { NavLink } from 'react-router-dom';
import {
  Activity,
  BookOpen,
  Briefcase,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MailPlus,
  RefreshCw,
  Target,
  type LucideIcon,
} from 'lucide-react';
import type { Role, User } from '../types';

export type NavItem = { to: string; label: string; icon: LucideIcon; roles: Role[] };

export const NAV: NavItem[] = [
  { to: '/app', label: 'Overview', icon: LayoutDashboard, roles: ['student'] },
  { to: '/app/assessment', label: 'Assessment', icon: ClipboardList, roles: ['student'] },
  { to: '/app/skill-gaps', label: 'Skill Gaps', icon: Target, roles: ['student'] },
  { to: '/app/resources', label: 'Learning Resources', icon: BookOpen, roles: ['student', 'teacher', 'admin'] },
  { to: '/app/jobs', label: 'Job Market', icon: Briefcase, roles: ['student', 'teacher', 'admin'] },
  { to: '/app/progress', label: 'Progress', icon: Activity, roles: ['student'] },
  { to: '/app/faculty', label: 'Faculty Insights', icon: GraduationCap, roles: ['teacher', 'admin'] },
  { to: '/app/admin/invitations', label: 'Mentor Invitations', icon: MailPlus, roles: ['admin'] },
];

const ROLE_LABEL: Record<Role, string> = { student: 'Student', teacher: 'Teacher / Mentor', admin: 'Administrator' };

export function Sidebar({
  user,
  online,
  onRefresh,
  onLogout,
}: {
  user: User;
  online: boolean;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">S</div>
        <div>
          <b>
            skill<span>align</span>
          </b>
          <small>WORKFORCE INTELLIGENCE</small>
        </div>
      </div>
      <div className="workspace">
        <GraduationCap />
        <div>
          <b>{user.full_name}</b>
          <small>{ROLE_LABEL[user.role]}</small>
        </div>
      </div>
      <nav aria-label="Main">
        {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/app'} className={({ isActive }) => (isActive ? 'active' : '')}>
            <n.icon size={18} />
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="side-bottom">
        <span className={online ? 'dot' : 'dot off'} />
        {online ? 'API connected' : 'API offline'}
        <button onClick={onRefresh}>
          <RefreshCw size={15} /> Refresh data
        </button>
        <button onClick={onLogout}>
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </aside>
  );
}
