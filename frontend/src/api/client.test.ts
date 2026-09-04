import { describe, expect, it, vi } from 'vitest';
import { request, streamSSE } from './client';
import { saveSession } from '../auth/session';

describe('API client', () => {
  it('adds the stored bearer token to JSON requests', async () => {
    saveSession({ accessToken: 'test-token', user: { user_id: 'u1', username: 'researcher' } });
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    await request<{ ok: boolean }>('/research/runs');
    expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer test-token');
  });

  it('leaves multipart content type to the browser boundary handler', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const formData = new FormData();
    formData.append('source_id', 'source-1');

    await request('/documents/upload', { method: 'POST', body: formData });

    expect(fetchMock.mock.calls[0][1].headers.has('Content-Type')).toBe(false);
  });

  it('parses SSE ids and JSON data', async () => {
    const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('id: run-1:2\ndata: {"event":"retrieval_event"}\n\n')); controller.close(); } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })));
    const events: { id?: string; data: { event: string } }[] = [];
    await streamSSE<{ event: string }>('/research/runs/run-1/events', { method: 'GET' }, (event) => events.push(event), new AbortController().signal);
    expect(events).toEqual([{ id: 'run-1:2', data: { event: 'retrieval_event' } }]);
  });

  it('raises a typed error for backend failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Forbidden' }), { status: 403 })));
    await expect(request('/research/runs/other')).rejects.toMatchObject({ status: 403, message: 'Forbidden' });
  });

  it('preserves FastAPI validation details for actionable auth errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ['body', 'username'], msg: 'String should match pattern' }] }), { status: 422 })));
    await expect(request('/users', { method: 'POST', body: JSON.stringify({ username: 'not valid' }) })).rejects.toMatchObject({ status: 422, message: 'body.username: String should match pattern' });
  });

  it('turns browser fetch failures into an actionable local-stack message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(request('/documents/upload', { method: 'POST', body: new FormData() })).rejects.toMatchObject({
      status: 0,
      message: 'The Anvikshiki API is unavailable. Start the backend and PostgreSQL services, then try again.',
    });
  });
});
