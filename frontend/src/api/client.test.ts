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
});
