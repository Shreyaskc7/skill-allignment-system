import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Alert } from './ui';

/** Shows a recoverable message instead of a blank page if a screen fails to render. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Screen failed to render', error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="panel">
        <Alert>
          This screen could not be displayed. Try another page or reload. If it keeps happening, report: “
          {this.state.error.message}”.
        </Alert>
        <button className="secondary" onClick={() => window.location.reload()}>
          Reload
        </button>
      </section>
    );
  }
}
