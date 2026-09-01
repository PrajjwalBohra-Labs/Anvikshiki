import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { KnowledgeGraphPage } from './KnowledgeGraphPage';

const api = vi.hoisted(() => ({ getRunProvenanceGraph: vi.fn(), listResearchRuns: vi.fn() }));
vi.mock('../../api/services', () => api);
vi.mock('../../routing', () => ({ navigate: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const graph = {
  nodes: [
    { node_id: 'source-node', node_type: 'SOURCE', entity_id: 'source-1', label: 'Source One', metadata: { source_type: 'PRIMARY' }, created_at: '2026-08-30T10:00:00Z' },
    { node_id: 'claim-node', node_type: 'CLAIM', entity_id: 'claim-1', label: 'A claim returned by the run.', metadata: { confidence: 0.8 }, created_at: '2026-08-30T10:01:00Z' },
  ],
  edges: [{ edge_id: 'edge-1', from_node_id: 'source-node', to_node_id: 'claim-node', relationship_type: 'SUPPORTS', metadata: {}, created_at: '2026-08-30T10:02:00Z' }],
};

describe('knowledge graph page', () => {
  it('renders only returned nodes and relationships with selectable metadata', async () => {
    api.getRunProvenanceGraph.mockResolvedValue(graph);
    render(<KnowledgeGraphPage runId="run-1" />);

    expect(await screen.findByRole('button', { name: /Source One/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /A claim returned by the run/ })).toBeInTheDocument();
    expect(screen.getByText('SUPPORTS')).toBeInTheDocument();
    expect(screen.getByText('PRIMARY')).toBeInTheDocument();
    expect(api.getRunProvenanceGraph).toHaveBeenCalledWith('run-1');
    fireEvent.click(screen.getByRole('button', { name: /A claim returned by the run/ }));
    expect(screen.getByRole('complementary', { name: 'Selected graph node' })).toHaveTextContent('confidence');
  });

  it('lists authenticated runs before a graph is selected', async () => {
    api.listResearchRuns.mockResolvedValue([{ run_id: 'run-2', query: 'A persisted investigation', domain: 'Epistemology', status: 'completed', started_at: '2026-08-30T10:00:00Z', finished_at: null }]);
    render(<KnowledgeGraphPage />);

    expect(await screen.findByText('A persisted investigation')).toBeInTheDocument();
    expect(api.listResearchRuns).toHaveBeenCalledOnce();
  });

  it('shows the backend empty graph state and does not invent nodes', async () => {
    api.getRunProvenanceGraph.mockResolvedValue({ nodes: [], edges: [] });
    render(<KnowledgeGraphPage runId="empty-run" />);

    expect(await screen.findByText('The backend returned an empty graph.')).toBeInTheDocument();
    expect(screen.getByText('No graph relationships were returned.')).toBeInTheDocument();
  });

  it('shows downstream errors as an accessible error state', async () => {
    api.getRunProvenanceGraph.mockRejectedValue(new Error('Internal database details must not be shown.'));
    render(<KnowledgeGraphPage runId="failed-run" />);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Knowledge graph could not be loaded.'));
    expect(screen.getByRole('alert')).not.toHaveTextContent('Internal database details');
  });

  it('does not turn an unauthorized run request into a data disclosure', async () => {
    api.getRunProvenanceGraph.mockRejectedValue(new ApiError(403, 'private backend detail'));
    render(<KnowledgeGraphPage runId="another-users-run" />);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('This research run is unavailable to the current session.'));
    expect(screen.getByRole('alert')).not.toHaveTextContent('private backend detail');
  });
});
