import {
  Activity,
  BookOpen,
  Briefcase,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  RefreshCw,
  Target,
  type LucideIcon,
} from 'lucide-react';
import type { Page } from '../types';

const NAV: { name: Page; icon: LucideIcon }[] = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'Assessment', icon: ClipboardList },
  { name: 'Skill Gaps', icon: Target },
  { name: 'Learning Resources', icon: BookOpen },
  { name: 'Job Market', icon: Briefcase },
  { name: 'Progress', icon: Activity },
  { name: 'Faculty Insights', icon: GraduationCap },
];

export function Sidebar({
  page,
  online,
  onNavigate,
  onRefresh,
}: {
  page: Page;
  online: boolean;
  onNavigate: (page: Page) => void;
  onRefresh: () => void;
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
          <b>MCA Workspace</b>
          <small>Student demo profile</small>
        </div>
      </div>
      <nav>
        {NAV.map((n) => (
          <button key={n.name} className={page === n.name ? 'active' : ''} onClick={() => onNavigate(n.name)}>
            <n.icon size={18} />
            {n.name}
          </button>
        ))}
      </nav>
      <div className="side-bottom">
        <span className={online ? 'dot' : 'dot off'} />
        {online ? 'API connected' : 'API offline'}
        <button onClick={onRefresh}>
          <RefreshCw size={15} /> Refresh data
        </button>
      </div>
    </aside>
  );
}
