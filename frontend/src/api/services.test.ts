import { describe, expect, it, vi } from 'vitest';

const client = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('./client', () => ({ request: client.request, requestBlob: vi.fn(), requestRoot: vi.fn(), streamSSE: vi.fn() }));

import { createEpistemicPosition, createNotebook, getNotebook, getRunProvenanceGraph, updateEpistemicPositionStatus } from './services';

describe('epistemic memory API services', () => {
  it('posts a position through the authenticated API contract', async () => {
    client.request.mockResolvedValue({ position_id: 'position-1' });
    const payload = { user_id: 'user-1', claim_statement: 'A valid claim.', position: 'tentative', confidence: 0.7, status: 'tentative' };

    await createEpistemicPosition(payload);

    expect(client.request).toHaveBeenCalledWith('/epistemic/positions', { method: 'POST', body: JSON.stringify(payload) });
  });

  it('encodes stable position ids for status updates', async () => {
    client.request.mockResolvedValue({ position_id: 'position/1' });
    const payload = { new_status: 'contested', change_reason: 'Needs review.' };

    await updateEpistemicPositionStatus('position/1', payload);

    expect(client.request).toHaveBeenCalledWith('/epistemic/positions/position%2F1/status', { method: 'PATCH', body: JSON.stringify(payload) });
  });

  it('requests the authenticated provenance graph for a run', async () => {
    client.request.mockResolvedValue({ nodes: [], edges: [] });

    await getRunProvenanceGraph('run/1');

    expect(client.request).toHaveBeenCalledWith('/research/runs/run%2F1/provenance/graph');
  });

  it('uses the authenticated notebook resource contract', async () => {
    client.request.mockResolvedValue({ notebook_id: 'notebook-1' });
    await createNotebook({ title: 'Notes', content: 'A note.' });
    expect(client.request).toHaveBeenCalledWith('/notebooks', { method: 'POST', body: JSON.stringify({ title: 'Notes', content: 'A note.' }) });

    await getNotebook('notebook/1');
    expect(client.request).toHaveBeenCalledWith('/notebooks/notebook%2F1');
  });
});
