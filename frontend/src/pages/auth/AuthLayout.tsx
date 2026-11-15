import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export function AuthLayout({ title, subtitle, children, footer }: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="auth-shell">
      <Link to="/" className="brand auth-brand" aria-label="SkillAlign home">
        <div className="brand-icon">S</div>
        <b>
          skill<span>align</span>
        </b>
      </Link>
      <main className="auth-card">
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
        {children}
      </main>
      {footer && <p className="auth-footer">{footer}</p>}
    </div>
  );
}
