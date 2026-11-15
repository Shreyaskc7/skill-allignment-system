import { useId, type ReactNode } from 'react';
import type { Career } from '../types';

export function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="metric">
      <div>
        {icon}
        <small>{label}</small>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

export function CareerSelect({
  careers,
  role,
  onChange,
}: {
  careers: Career[];
  role: string;
  onChange: (role: string) => void;
}) {
  const id = useId();
  return (
    <>
      <label htmlFor={id}>Target career role</label>
      <select id={id} value={role} onChange={(e) => onChange(e.target.value)}>
        {careers.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </>
  );
}
