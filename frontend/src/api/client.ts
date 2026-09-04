import { getAccessToken } from '../auth/session';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (typeof body === 'object' && body !== null && 'error' in body && typeof body.error === 'string') {
    return body.error;
  }
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => {
        if (typeof item !== 'object' || item === null) return null;
        const value = item as { loc?: unknown; msg?: unknown };
        const message = typeof value.msg === 'string' ? value.msg : null;
        if (!message) return null;
        const location = Array.isArray(value.loc) ? value.loc.filter((part): part is string | number => typeof part === 'string' || typeof part === 'number').join('.') : '';
        return location ? `${location}: ${message}` : message;
      }).filter((message): message is string => Boolean(message));
      if (messages.length > 0) return messages.join(' ');
      return 'The request did not pass validation.';
    }
  }
  return fallback;
}

function authenticatedHeaders(options: RequestInit): Headers {
  const headers = new Headers(options.headers);
  const token = getAccessToken();
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

function notifyUnauthorized(status: number): void {
  if (status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('anvikshiki:auth-expired'));
}

function networkErrorMessage(error: unknown, resource: string): string {
  if (error instanceof TypeError && /fetch|network|connect/i.test(error.message)) {
    return `The Anvikshiki ${resource} is unavailable. Start the backend and PostgreSQL services, then try again.`;
  }
  return error instanceof Error ? error.message : `The Anvikshiki ${resource} could not be reached.`;
}

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = authenticatedHeaders(options);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new ApiError(0, networkErrorMessage(error, 'API'));
  }

  const body = await response.json().catch(() => undefined);
  if (!response.ok) {
    notifyUnauthorized(response.status);
    throw new ApiError(response.status, errorMessage(body, `Request failed with status ${response.status}.`), body);
  }
  return body as T;
}

export async function requestRoot<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const origin = new URL(API_BASE_URL, window.location.origin).origin;
  const url = origin + (endpoint.startsWith('/') ? endpoint : '/' + endpoint);
  const headers = authenticatedHeaders(options);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new ApiError(0, networkErrorMessage(error, 'API'));
  }
  const body = await response.json().catch(() => undefined);
  if (!response.ok) {
    notifyUnauthorized(response.status);
    throw new ApiError(response.status, errorMessage(body, 'Request failed with status ' + response.status + '.'), body);
  }
  return body as T;
}

export interface SSEEvent<T> {
  data: T;
  id?: string;
}

export async function streamSSE<T>(
  endpoint: string,
  options: RequestInit,
  onEvent: (event: SSEEvent<T>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = authenticatedHeaders(options);
  headers.set('Accept', 'text/event-stream');
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers, signal });
  } catch (error) {
    if (signal?.aborted) return;
    throw new ApiError(0, networkErrorMessage(error, 'research service'));
  }

  if (!response.ok) {
    notifyUnauthorized(response.status);
    const body = await response.json().catch(() => undefined);
    throw new ApiError(response.status, errorMessage(body, `Research stream failed with status ${response.status}.`), body);
  }
  if (!response.body) throw new ApiError(0, 'Research stream returned no readable body.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const lines = frame.split(/\r?\n/);
        const data = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n');
        const id = lines.find((line) => line.startsWith('id:'))?.slice(3).trim();
        if (!data) continue;
        try {
          onEvent({ data: JSON.parse(data) as T, id });
        } catch {
          // Ignore malformed individual frames; the stream remains usable.
        }
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

export async function requestBlob(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = authenticatedHeaders(options);
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new ApiError(0, networkErrorMessage(error, 'API'));
  }
  if (!response.ok) {
    notifyUnauthorized(response.status);
    const body = await response.json().catch(() => undefined);
    throw new ApiError(response.status, errorMessage(body, `Request failed with status ${response.status}.`), body);
  }
  return response.blob();
}
