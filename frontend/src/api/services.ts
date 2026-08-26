import { request, requestRoot, streamSSE } from './client';
import type {
  DialogueTurnDTO,
  DocumentUploadResponseDTO,
  EpistemicPositionDTO,
  HealthDTO,
  ResearchEventDTO,
  ResearchRunRequestDTO,
  SearchResponseDTO,
  PassageDTO,
  SourceCreateDTO,
  SourceDTO,
} from '../types';

export function startResearch(
  payload: ResearchRunRequestDTO,
  onEvent: (event: ResearchEventDTO) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE<ResearchEventDTO>(
    '/research/run/stream',
    { method: 'POST', body: JSON.stringify(payload) },
    ({ data }) => onEvent(data),
    signal,
  );
}

export function searchPassages(query: string, sourceType?: string, topK = 5): Promise<SearchResponseDTO> {
  const params = new URLSearchParams({ query, top_k: String(topK) });
  if (sourceType) params.set('source_type', sourceType);
  return request<SearchResponseDTO>(`/search/?${params.toString()}`);
}

export function listSources(): Promise<SourceDTO[]> {
  return request<SourceDTO[]>('/sources/');
}

export function createSource(payload: SourceCreateDTO): Promise<SourceDTO> {
  return request<SourceDTO>('/sources/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function uploadDocument(sourceId: string, file: File): Promise<DocumentUploadResponseDTO> {
  const formData = new FormData();
  formData.append('source_id', sourceId);
  formData.append('file', file);
  return request<DocumentUploadResponseDTO>('/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export function getDocumentPassages(documentId: string): Promise<PassageDTO[]> {
  return request<PassageDTO[]>(`/documents/${encodeURIComponent(documentId)}/passages`);
}

export function getHealth(): Promise<HealthDTO> {
  return requestRoot<HealthDTO>('/health');
}

export function getEpistemicPositions(userId: string): Promise<EpistemicPositionDTO[]> {
  return request<EpistemicPositionDTO[]>(`/epistemic/user/${encodeURIComponent(userId)}/positions`);
}

export function executeDialogue(userUtterance: string, dialogueMode = 'socratic'): Promise<DialogueTurnDTO> {
  return request<DialogueTurnDTO>('/dialogue/turn', {
    method: 'POST',
    body: JSON.stringify({ user_utterance: userUtterance, dialogue_mode: dialogueMode }),
  });
}
