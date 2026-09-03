import { request, requestBlob, requestRoot, streamSSE } from './client';
import type {
  AuthUserDTO,
  ClaimEvidenceDTO,
  DialogueTurnDTO,
  DocumentDTO,
  DocumentUploadResponseDTO,
  EpistemicPositionDTO,
  EvidenceTraceDTO,
  HealthDTO,
  BackgroundJobDTO,
  ProvenanceGraphDTO,
  ResearchExportDTO,
  ResearchQuestionDetailDTO,
  ResearchQuestionSummaryDTO,
  ResearchEventDTO,
  ResearchRunDetailDTO,
  ResearchRunSummaryDTO,
  ResearchRunRequestDTO,
  SearchResponseDTO,
  PassageDTO,
  SpecialistAnalysisDTO,
  SourceCreateDTO,
  SourceDTO,
  UserResponseDTO,
  WebAcquisitionResponseDTO,
} from '../types';

export function startResearch(
  payload: ResearchRunRequestDTO,
  onEvent: (event: ResearchEventDTO, id?: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE<ResearchEventDTO>(
    '/research/run/stream',
    { method: 'POST', body: JSON.stringify(payload) },
    ({ data, id }) => onEvent(data, id),
    signal,
  );
}

export function replayResearchEvents(
  runId: string,
  lastEventId: string | undefined,
  onEvent: (event: ResearchEventDTO, id?: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers();
  if (lastEventId) headers.set('Last-Event-ID', lastEventId);
  return streamSSE<ResearchEventDTO>(
    `/research/runs/${encodeURIComponent(runId)}/events`,
    { method: 'GET', headers },
    ({ data, id }) => onEvent(data, id),
    signal,
  );
}

export function registerUser(username: string): Promise<UserResponseDTO> {
  return request<UserResponseDTO>('/users', { method: 'POST', body: JSON.stringify({ username }) });
}

export function getCurrentUser(): Promise<AuthUserDTO> {
  return request<AuthUserDTO>('/auth/me');
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' });
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

export function listDocuments(sourceId?: string): Promise<DocumentDTO[]> {
  const params = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : '';
  return request<DocumentDTO[]>(`/documents/${params}`);
}

export function getDocument(documentId: string): Promise<DocumentDTO> {
  return request<DocumentDTO>(`/documents/${encodeURIComponent(documentId)}`);
}

export function downloadDocument(documentId: string): Promise<Blob> {
  return requestBlob(`/documents/${encodeURIComponent(documentId)}/file`);
}

export function acquireWebSource(url: string, sourceTitle?: string): Promise<WebAcquisitionResponseDTO> {
  return request<WebAcquisitionResponseDTO>('/web/acquire', {
    method: 'POST',
    body: JSON.stringify({ url, ...(sourceTitle ? { source_title: sourceTitle } : {}) }),
  });
}

export function listResearchRuns(options: { status?: string; limit?: number; offset?: number } = {}): Promise<ResearchRunSummaryDTO[]> {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (options.limit !== undefined) params.set('limit', String(options.limit));
  if (options.offset !== undefined) params.set('offset', String(options.offset));
  return request<ResearchRunSummaryDTO[]>(`/research/runs${params.toString() ? `?${params.toString()}` : ''}`);
}

export function getResearchRun(runId: string): Promise<ResearchRunDetailDTO> {
  return request<ResearchRunDetailDTO>(`/research/runs/${encodeURIComponent(runId)}`);
}

export function listResearchQuestions(options: { limit?: number; offset?: number } = {}): Promise<ResearchQuestionSummaryDTO[]> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) params.set('limit', String(options.limit));
  if (options.offset !== undefined) params.set('offset', String(options.offset));
  return request<ResearchQuestionSummaryDTO[]>(`/research/questions${params.toString() ? `?${params.toString()}` : ''}`);
}

export function getResearchQuestion(questionId: string): Promise<ResearchQuestionDetailDTO> {
  return request<ResearchQuestionDetailDTO>(`/research/questions/${encodeURIComponent(questionId)}`);
}

export function getRunClaims(runId: string): Promise<ClaimEvidenceDTO[]> {
  return request<ClaimEvidenceDTO[]>(`/research/runs/${encodeURIComponent(runId)}/claims`);
}

export function getRunAnalysis(runId: string): Promise<SpecialistAnalysisDTO> {
  return request<SpecialistAnalysisDTO>(`/research/runs/${encodeURIComponent(runId)}/analysis`);
}

export function getRunProvenance(runId: string): Promise<EvidenceTraceDTO[]> {
  return request<EvidenceTraceDTO[]>(`/research/runs/${encodeURIComponent(runId)}/provenance`);
}

export function getRunProvenanceGraph(runId: string): Promise<ProvenanceGraphDTO> {
  return request<ProvenanceGraphDTO>(`/research/runs/${encodeURIComponent(runId)}/provenance/graph`);
}

export function exportResearchRun(runId: string): Promise<ResearchExportDTO> {
  return request<ResearchExportDTO>(`/research/runs/${encodeURIComponent(runId)}/export`);
}

export function listBackgroundJobs(): Promise<BackgroundJobDTO[]> {
  return request<BackgroundJobDTO[]>('/research/jobs');
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
