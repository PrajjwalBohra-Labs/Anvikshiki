import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useResearchStream } from './useResearchStream';
import type { ResearchEventDTO } from '../types';

const services = vi.hoisted(() => ({ startResearch: vi.fn(), replayResearchEvents: vi.fn() }));
vi.mock('../api/services', () => services);

const completed: ResearchEventDTO = {
  event: 'research_completed', event_id: 'run-1:2', sequence: 2, run_id: 'run-1', status: 'validated',
  result: { run_id: 'run-1', query: 'What is evidence?', domain: 'Epistemology', validation_status: 'validated', final_response: 'A measured answer.', validated_claims_count: 1, retrieved_passages: [], claims: [], specialist_analysis: { philosophical_arguments: [], source_criticisms: [], scientific_analyses: [], comparisons: [], challenges: [] }, validation: {} },
};

describe('research stream state', () => {
  beforeEach(() => { services.startResearch.mockReset(); services.replayResearchEvents.mockReset(); });

  it('deduplicates event ids and preserves the completed result', async () => {
    services.startResearch.mockImplementation(async (_payload: unknown, onEvent: (event: ResearchEventDTO, id: string) => void) => {
      const started: ResearchEventDTO = { event: 'research_started', event_id: 'run-1:1', sequence: 1, run_id: 'run-1', query: 'What is evidence?', thread_id: 'thread-1' };
      onEvent(started, started.event_id); onEvent(started, started.event_id); onEvent(completed, completed.event_id);
    });
    const { result } = renderHook(() => useResearchStream('u1'));
    await act(async () => { await result.current.run('What is evidence?', 'Epistemology'); });
    expect(result.current.state.status).toBe('completed');
    expect(result.current.state.activity).toHaveLength(2);
    expect(result.current.state.finalResponse).toBe('A measured answer.');
    expect(result.current.state.runId).toBe('run-1');
  });

  it('moves to cancelled when the active stream is aborted', async () => {
    services.startResearch.mockImplementation((_payload: unknown, _onEvent: unknown, signal: AbortSignal) => new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true })));
    const { result } = renderHook(() => useResearchStream('u1'));
    let runPromise: Promise<void> | undefined;
    await act(async () => { runPromise = result.current.run('A cancellable question'); });
    await act(async () => { result.current.cancel(); await runPromise; });
    expect(result.current.state.status).toBe('cancelled');
  });
});
