import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, request } from '../api/client';
import { clearSession, getSession, saveSession, type StoredSession } from './session';
import type { AuthUserDTO, UserResponseDTO } from '../types';

interface AuthContextValue {
  user: AuthUserDTO | null;
  initializing: boolean;
  error: string;
  register: (username: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => getSession());
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      if (!session) { setInitializing(false); return; }
      try {
        const user = await request<AuthUserDTO>('/auth/me');
        if (active) {
          const next = { ...session, user };
          saveSession(next);
          setSession(next);
        }
      } catch (reason) {
        if (active) {
          if (reason instanceof ApiError && reason.status === 401) {
            clearSession();
            setSession(null);
            setError('Your session is no longer valid. Enter your username to authenticate again.');
          } else {
            setError(reason instanceof Error ? reason.message : 'The backend could not validate the local session.');
          }
        }
      } finally {
        if (active) setInitializing(false);
      }
    };
    void bootstrap();
    const expire = () => { clearSession(); setSession(null); setError('Your session is no longer valid.'); };
    window.addEventListener('anvikshiki:auth-expired', expire);
    return () => { active = false; window.removeEventListener('anvikshiki:auth-expired', expire); };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    initializing,
    error,
    register: async (username: string) => {
      setError('');
      try {
        let response: UserResponseDTO;
        try {
          response = await request<UserResponseDTO>('/auth/login', { method: 'POST', body: JSON.stringify({ username }) });
        } catch (reason) {
          if (!(reason instanceof ApiError) || reason.status !== 404) throw reason;
          response = await request<UserResponseDTO>('/users', { method: 'POST', body: JSON.stringify({ username }) });
        }
        if (!response.access_token) throw new Error('The backend did not return a session token.');
        const next = { accessToken: response.access_token, user: { user_id: response.user_id, username: response.username } };
        saveSession(next);
        setSession(next);
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : 'A local session could not be created.';
        setError(message);
        throw reason;
      }
    },
    logout: async () => {
      try { if (session) await request<void>('/auth/logout', { method: 'POST' }); }
      finally { clearSession(); setSession(null); }
    },
  }), [error, initializing, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
