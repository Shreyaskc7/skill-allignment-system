import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { postJson, refreshSession, request, setAccessToken, setSessionExpiredHandler } from '../api/client';
import type { User } from '../types';

type Session = { access_token: string; user: User };

export type RegisterInput = {
  full_name: string;
  email: string;
  phone?: string;
  password: string;
  confirm_password: string;
  terms_accepted: boolean;
};

type AuthState = {
  user: User | null;
  status: 'loading' | 'authenticated' | 'anonymous';
  login: (email: string, password: string) => Promise<User>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState['status']>('loading');

  const endSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus('anonymous');
  }, []);

  // Restore the session after a page reload using the HttpOnly refresh cookie.
  useEffect(() => {
    setSessionExpiredHandler(endSession);
    refreshSession<Session>()
      .then((s) => {
        if (s) {
          setUser(s.user);
          setStatus('authenticated');
        } else endSession();
      })
      .catch(endSession);
  }, [endSession]);

  const login = useCallback(async (email: string, password: string) => {
    const s = await request<Session>('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(s.access_token);
    setUser(s.user);
    setStatus('authenticated');
    return s.user;
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    await postJson('/api/v1/auth/register', { ...input, phone: input.phone || null });
  }, []);

  const logout = useCallback(async () => {
    try {
      await postJson('/api/v1/auth/logout', {});
    } finally {
      endSession();
    }
  }, [endSession]);

  const value = useMemo(() => ({ user, status, login, register, logout }), [user, status, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** The landing route for each role after login. */
export function homeFor(user: User | null): string {
  if (!user) return '/login';
  return user.role === 'student' ? '/app' : user.role === 'admin' ? '/app/admin' : '/app/mentor';
}
