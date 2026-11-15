import { createContext, useCallback, useContext, useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, X } from 'lucide-react';

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="spin" aria-hidden="true" />;
}

export function LoadingScreen({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <Spinner size={28} />
      <span>{label}</span>
    </div>
  );
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'success' | 'info'; children: ReactNode }) {
  const Icon = kind === 'success' ? CheckCircle2 : AlertCircle;
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon size={17} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string };

export function Field({ label, error, hint, id, ...input }: FieldProps) {
  const auto = useId();
  const fieldId = id ?? auto;
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;
  return (
    <div className={'field' + (error ? ' has-error' : '')}>
      <label htmlFor={fieldId}>{label}</label>
      <input id={fieldId} aria-invalid={!!error} aria-describedby={describedBy} {...input} />
      {error ? (
        <small id={`${fieldId}-error`} className="field-error">
          {error}
        </small>
      ) : (
        hint && (
          <small id={`${fieldId}-hint`} className="field-hint">
            {hint}
          </small>
        )
      )}
    </div>
  );
}

export function PasswordField(props: Omit<FieldProps, 'type'>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-field">
      <Field {...props} type={visible ? 'text' : 'password'} />
      <button
        type="button"
        className="reveal"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button className="primary block" type="submit" disabled={busy} aria-busy={busy}>
      {busy && <Spinner />} {children}
    </button>
  );
}

// ------------------------------------------------------------------ toasts

type Toast = { id: number; kind: 'success' | 'error' | 'info'; message: string };
const ToastContext = createContext<(kind: Toast['kind'], message: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = (id: number) => setToasts((t) => t.filter((x) => x.id !== id));
  const push = useCallback((kind: Toast['kind'], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, kind, message }]);
    setTimeout(() => dismiss(id), kind === 'error' ? 7000 : 4000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
            <span>{t.message}</span>
            <button aria-label="Dismiss notification" onClick={() => dismiss(t.id)}>
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ------------------------------------------------------------------ confirm dialog

export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.key === 'Escape' && onCancel()}
      >
        <h3 id="dialog-title">{title}</h3>
        <div className="dialog-body">{children}</div>
        <div className="dialog-actions">
          <button className="secondary" onClick={onCancel} autoFocus>
            Cancel
          </button>
          <button className="primary danger" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
