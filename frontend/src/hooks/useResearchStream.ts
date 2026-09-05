import { useCallback, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { replayResearchEvents, startResearch } from '../api/services';
import type { ResearchActivityItem, ResearchEventDTO, ResearchResultDTO } from '../types';

type RunStatus = 'idle' | 'streaming' | 'completed' | 'failed' | 'cancelled';

export interface ResearchStreamState {
  status: RunStatus;
  query: string;
  runId?: string;
  activity: ResearchActivityItem[];
  finalResponse: string;
  validationStatus?: string;
  validatedClaimsCount?: number;
  result?: ResearchResultDTO;
  error?: string;
}

const initialState: ResearchStreamState = {
  status: 'idle',
  query: '',
  activity: [],
  finalResponse: '',
};

export function useResearchStream(userId: string) {
  const [state, setState] = useState<ResearchStreamState>(initialState);
  const controllerRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setState((current) => ({ ...current, status: 'cancelled', error: undefined }));
  }, []);

  const run = useCallback(async (query: string, domain?: string, includeWeb = false) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const seen = new Set<string>();
    let runId: string | undefined;
    let lastEventId: string | undefined;
    let completed = false;
    setState({ ...initialState, status: 'streaming', query });

    const handleEvent = (event: ResearchEventDTO, receivedId?: string) => {
      const eventId = receivedId ?? event.event_id;
      const eventKey = eventId || `${event.run_id}:${event.sequence}`;
      if (seen.has(eventKey)) return;
      seen.add(eventKey);
      runId = event.run_id;
      lastEventId = eventId;

      if (event.event === 'research_started') {
        setState((current) => ({
          ...current,
          runId,
          activity: [...current.activity, { key: eventKey, event: event.event, status: 'started', summary: 'Research run started.' }],
        }));
        return;
      }
      if (event.event === 'research_completed') {
        completed = true;
        const result = event.result;
        setState((current) => ({
          ...current,
          status: 'completed',
          runId,
          result,
          finalResponse: result.final_response,
          validationStatus: result.validation_status,
          validatedClaimsCount: result.validated_claims_count,
          activity: [...current.activity, { key: eventKey, event: event.event, status: event.status, summary: 'Research synthesis completed.' }],
        }));
        return;
      }
      if (event.event === 'research_error') {
        setState((current) => ({ ...current, runId, status: 'failed', error: event.error }));
        return;
      }
      setState((current) => ({
        ...current,
        runId,
        activity: [...current.activity, { key: eventKey, event: event.event, node: event.node, status: event.status, summary: event.summary }],
      }));
    };

    try {
      await startResearch({ user_id: userId, query, domain, include_web: includeWeb }, handleEvent, controller.signal);
      if (!completed && !controller.signal.aborted) {
        if (runId && lastEventId) await replayResearchEvents(runId, lastEventId, handleEvent, controller.signal);
        setState((current) => current.status === 'streaming' ? { ...current, status: 'failed', error: 'Research stream ended before completion.' } : current);
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      try {
        if (runId && lastEventId) await replayResearchEvents(runId, lastEventId, handleEvent, controller.signal);
      } catch {
        // Keep the original transport error as the user-facing message.
      }
      setState((current) => current.status === 'streaming' ? {
        ...current,
        status: 'failed',
        error: error instanceof ApiError ? error.message : 'Research could not be completed.',
      } : current);
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [userId]);

  return { state, run, cancel };
}
