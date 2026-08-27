export const SESSION_STORAGE_KEY = 'anvikshiki.session';

export interface StoredSession {
  accessToken: string;
  user: { user_id: string; username: string };
}

export function getSession(): StoredSession | null {
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || !('accessToken' in parsed) || !('user' in parsed)) return null;
    const value = parsed as { accessToken?: unknown; user?: unknown };
    if (typeof value.accessToken !== 'string' || typeof value.user !== 'object' || value.user === null) return null;
    const user = value.user as { user_id?: unknown; username?: unknown };
    if (typeof user.user_id !== 'string' || typeof user.username !== 'string') return null;
    return { accessToken: value.accessToken, user: { user_id: user.user_id, username: user.username } };
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return getSession()?.accessToken ?? null;
}

export function saveSession(session: StoredSession): void {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}
