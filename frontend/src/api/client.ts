const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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
    if (Array.isArray(detail)) return 'The request did not pass validation.';
  }
  return fallback;
}

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new ApiError(0, error instanceof Error ? error.message : 'Network connection failure');
  }

  const body = await response.json().catch(() => undefined);
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(body, `Request failed with status ${response.status}.`), body);
  }
  return body as T;
}

export async function requestRoot<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const origin = new URL(API_BASE_URL, window.location.origin).origin;
  const url = origin + (endpoint.startsWith('/') ? endpoint : '/' + endpoint);
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new ApiError(0, error instanceof Error ? error.message : 'Network connection failure');
  }
  const body = await response.json().catch(() => undefined);
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, 'Request failed with status ' + response.status + '.'), body);
  return body as T;
}

export interface SSEEvent<T> {
  data: T;
}

export async function streamSSE<T>(
  endpoint: string,
  options: RequestInit,
  onEvent: (event: SSEEvent<T>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers);
  headers.set('Accept', 'text/event-stream');
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers, signal });
  } catch (error) {
    if (signal?.aborted) return;
    throw new ApiError(0, error instanceof Error ? error.message : 'Research stream connection failed.');
  }

  if (!response.ok) {
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
        const data = frame
          .split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trim())
          .join('\n');
        if (!data) continue;
        try {
          onEvent({ data: JSON.parse(data) as T });
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
