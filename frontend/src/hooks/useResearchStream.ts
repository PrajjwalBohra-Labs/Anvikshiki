import { useCallback, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { startResearch } from '../api/services';
import type { ResearchActivityItem, ResearchClaimDTO, ResearchEventDTO } from '../types';

type RunStatus = 'idle' | 'streaming' | 'completed' | 'failed' | 'cancelled';

export interface ResearchStreamState {
  status: RunStatus;
  query: string;
  activity: ResearchActivityItem[];
  finalResponse: string;
  validationStatus?: string;
  validatedClaimsCount?: number;
  claims: ResearchClaimDTO[];
  error?: string;
}

const initialState: ResearchStreamState = {
  status: 'idle',
  query: '',
  activity: [],
  finalResponse: '',
  claims: [],
};

export function useResearchStream(userId: string) {
  const [state, setState] = useState<ResearchStreamState>(initialState);
  const controllerRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setState((current) => ({ ...current, status: 'cancelled' }));
  }, []);

  const run = useCallback(async (query: string, domain?: string) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const seen = new Set<string>();
    setState({ ...initialState, status: 'streaming', query });

    const handleEvent = (event: ResearchEventDTO) => {
      const eventKey = JSON.stringify(event);
      if (seen.has(eventKey)) return;
      seen.add(eventKey);

      if (event.event === 'research_started') {
        setState((current) => ({
          ...current,
          activity: [...current.activity, { key: eventKey, event: event.event, status: 'started', summary: 'Research run started.' }],
        }));
        return;
      }
      if (event.event === 'research_completed') {
        setState((current) => ({
          ...current,
          status: 'completed',
          finalResponse: event.final_response,
          validationStatus: event.validation_status,
          validatedClaimsCount: event.validated_claims_count,
          activity: [...current.activity, { key: eventKey, event: event.event, status: event.validation_status, summary: 'Research synthesis completed.' }],
        }));
        return;
      }
      setState((current) => ({
        ...current,
        activity: [...current.activity, { key: eventKey, event: event.event, node: event.node, status: event.status, summary: event.summary }],
      }));
    };

    try {
      await startResearch({ user_id: userId, query, domain }, handleEvent, controller.signal);
      setState((current) => current.status === 'streaming' ? { ...current, status: 'failed', error: 'Research stream ended before completion.' } : current);
    } catch (error) {
      if (controller.signal.aborted) return;
      setState((current) => ({
        ...current,
        status: 'failed',
        error: error instanceof ApiError ? error.message : 'Research could not be completed.',
      }));
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [userId]);

  return { state, run, cancel };
}
