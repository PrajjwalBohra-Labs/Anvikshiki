export type SourceType =
  | 'PRIMARY'
  | 'SECONDARY'
  | 'TRANSLATION'
  | 'COMMENTARY'
  | 'DISCOVERY_ONLY'
  | 'UNVERIFIED';

export type ClaimType =
  | 'DIRECT_SOURCE_CLAIM'
  | 'TRANSLATION'
  | 'SCHOLARLY_INTERPRETATION'
  | 'SCIENTIFIC_FINDING'
  | 'MODEL_SYNTHESIS'
  | 'INFERENCE'
  | 'ANALOGY'
  | 'HYPOTHESIS'
  | 'SPECULATION'
  | 'UNCERTAIN';

export type EvidenceStatus =
  | 'supported'
  | 'plausible'
  | 'contested'
  | 'weakly_supported'
  | 'unresolved'
  | 'insufficient_evidence';

export type RelationType = 'SUPPORTS' | 'CONTRADICTS' | 'QUALIFIES';
export type DialogueRole = 'user' | 'assistant' | 'system';

export interface MessageDTO {
  message_id: string;
  role: DialogueRole;
  content: string;
  research_run_id?: string | null;
  citations: Record<string, unknown>[];
  created_at: string;
}

export interface ConversationDTO {
  conversation_id: string;
  title?: string | null;
  created_at: string;
  messages: MessageDTO[];
}

export interface DialogueTurnDTO {
  response_text: string;
  dialogue_mode: string;
  disagrees_with_user: boolean;
  evidence_linked: boolean;
  preserves_uncertainty: boolean;
  source_title?: string | null;
}

export interface SourceCreateDTO {
  title: string;
  author?: string | null;
  historical_era?: string | null;
  original_language?: string | null;
  source_type: SourceType;
  reference_url?: string | null;
}

export interface DocumentUploadResponseDTO {
  document_id: string;
  checksum_sha256: string;
  mime_type: string;
  total_pages?: number | null;
  passages_count: number;
}

export interface ResearchRunRequestDTO {
  user_id: string;
  query: string;
  domain?: string;
  depth?: string;
}

export interface AuthUserDTO {
  user_id: string;
  username: string;
}

export interface UserResponseDTO extends AuthUserDTO {
  created_at: string;
  access_token?: string | null;
}

export interface ResearchQuestionSummaryDTO {
  question_id: string;
  user_id?: string | null;
  main_question: string;
  domain?: string | null;
  research_status: string;
  created_at: string;
  run_ids: string[];
}

export interface ResearchQuestionDetailDTO extends ResearchQuestionSummaryDTO {
  subquestions: string[];
  scope?: string | null;
  constraints: string[];
  user_position?: string | null;
  open_questions: string[];
}

export interface ResearchRunSummaryDTO {
  run_id: string;
  research_question_id?: string | null;
  thread_id?: string | null;
  user_id?: string | null;
  query: string;
  domain?: string | null;
  depth?: string | null;
  status: string;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
}

export interface ResearchStepDTO {
  step_name: string;
  step_type: string;
  status: string;
  payload?: Record<string, unknown> | null;
  event_id?: string | null;
  event_sequence?: number | null;
  created_at: string;
}

export interface ResearchPassageDTO {
  passage_id: string;
  source_id?: string | null;
  source_title: string;
  content: string;
  page_number?: number | null;
  source_type?: string | null;
  retrieval_channels: string[];
}

export interface ValidatedClaimDTO {
  claim_id?: string | null;
  statement: string;
  claim_type?: string | null;
  passage_id?: string | null;
  source_title?: string | null;
  confidence: number;
  is_verified: boolean;
  reason?: string | null;
}

export interface SpecialistAnalysisDTO {
  philosophical_arguments: Record<string, unknown>[];
  source_criticisms: Record<string, unknown>[];
  scientific_analyses: Record<string, unknown>[];
  comparisons: Record<string, unknown>[];
  challenges: Record<string, unknown>[];
}

export interface ResearchResultDTO {
  run_id: string;
  query: string;
  domain?: string | null;
  validation_status: string;
  final_response: string;
  validated_claims_count: number;
  retrieved_passages: ResearchPassageDTO[];
  claims: ValidatedClaimDTO[];
  specialist_analysis: SpecialistAnalysisDTO;
  validation: Record<string, unknown>;
}

export interface ResearchRunDetailDTO extends ResearchRunSummaryDTO {
  output_references?: Record<string, unknown> | null;
  steps: ResearchStepDTO[];
  result?: ResearchResultDTO | null;
}

export interface EvidenceLinkDTO {
  evidence_link_id: string;
  claim_id?: string | null;
  premise_id?: string | null;
  passage_id: string;
  relation_type: RelationType | string;
  confidence_weight: number;
}

export interface ClaimEvidenceDTO {
  claim_id: string;
  statement: string;
  claim_type: string;
  provenance_id?: string | null;
  confidence: number;
  lifecycle_status: string;
  evidence_links: EvidenceLinkDTO[];
}

export interface ProvenanceSourceDTO {
  source_id: string;
  title: string;
  author?: string | null;
  historical_era?: string | null;
  original_language?: string | null;
  source_type: string;
  reference_url?: string | null;
}

export interface ProvenanceDocumentDTO {
  document_id: string;
  source_id: string;
  checksum_sha256: string;
  mime_type: string;
  original_filename?: string | null;
  total_pages?: number | null;
}

export interface ProvenancePassageDTO {
  passage_id: string;
  document_id: string;
  page_number?: number | null;
  content: string;
  ocr_confidence?: number | null;
  extraction_uncertainty: boolean;
  language: string;
}

export interface EvidenceTraceDTO {
  evidence_link_id: string;
  claim_id?: string | null;
  premise_id?: string | null;
  relation_type: string;
  confidence_weight: number;
  passage: ProvenancePassageDTO;
  document: ProvenanceDocumentDTO;
  source: ProvenanceSourceDTO;
  source_lineage: Record<string, unknown>[];
}

export interface ProvenanceNodeDTO {
  node_id: string;
  node_type: string;
  entity_id: string;
  label: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ProvenanceEdgeDTO {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  relationship_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ProvenanceGraphDTO {
  nodes: ProvenanceNodeDTO[];
  edges: ProvenanceEdgeDTO[];
}

export interface DocumentDTO {
  document_id: string;
  source_id: string;
  checksum_sha256: string;
  mime_type: string;
  original_filename?: string | null;
  total_pages?: number | null;
  created_at: string;
  passages_count: number;
}

export interface WebAcquisitionResponseDTO {
  source: SourceDTO;
  document: DocumentDTO;
}

export interface ResearchClaimDTO {
  id?: string;
  statement: string;
  claim_type?: ClaimType | string;
  pramana_type?: string | null;
  confidence_score?: number;
  confidence?: number;
  status?: EvidenceStatus | string;
  [key: string]: unknown;
}

export interface ResearchEventStarted {
  event: 'research_started';
  event_id: string;
  sequence: number;
  run_id: string;
  query: string;
  thread_id: string;
}

export interface ResearchEventNode {
  event: `${string}_event`;
  event_id: string;
  sequence: number;
  run_id: string;
  node: string;
  status: string;
  summary: string;
}

export interface ResearchEventCompleted {
  event: 'research_completed';
  event_id: string;
  sequence: number;
  run_id: string;
  status: string;
  validation_status?: string;
  final_response?: string;
  validated_claims_count?: number;
  result: ResearchResultDTO;
}

export interface ResearchEventError {
  event: 'research_error';
  event_id: string;
  sequence: number;
  run_id: string;
  error: string;
}

export type ResearchEventDTO = ResearchEventStarted | ResearchEventNode | ResearchEventCompleted | ResearchEventError;

export interface SearchResultDTO {
  passage_id: string;
  source_id: string;
  source_title: string;
  content: string;
  page_number?: number | null;
  relevance_score: number;
  citation_string: string;
}

export interface SearchResponseDTO {
  query: string;
  total_results: number;
  results: SearchResultDTO[];
}

export interface SourceDTO {
  id: string;
  title: string;
  author?: string | null;
  historical_era?: string | null;
  original_language?: string | null;
  source_type: SourceType;
  reference_url?: string | null;
}

export interface PassageDTO {
  id: string;
  page_number?: number | null;
  content: string;
  ocr_confidence: number;
  extraction_uncertainty: boolean;
  language: string;
}

export interface EpistemicPositionDTO {
  position_id: string;
  claim_statement: string;
  position: string;
  confidence: number;
  status: string;
  supporting_evidence?: Record<string, unknown>[];
  counterarguments?: Record<string, unknown>[];
  updated_at: string;
  history: Record<string, unknown>[];
}

export interface EpistemicPositionCreateDTO {
  user_id: string;
  claim_statement: string;
  position: string;
  confidence: number;
  supporting_evidence?: Record<string, unknown>[];
  counterarguments?: Record<string, unknown>[];
  status?: string;
}

export interface EpistemicPositionUpdateDTO {
  new_status: string;
  change_reason?: string;
}

export interface ResearchContinuityResponseDTO {
  research_question_id: string;
  main_question: string;
  subquestions: string[];
  scope?: string | null;
  domain?: string | null;
  research_status: string;
  established_findings: string[];
  unresolved_questions: string[];
  user_positions: Record<string, unknown>[];
  evidence_trail: Record<string, unknown>[];
  research_timeline: Record<string, unknown>[];
  suggested_next_step: string;
}

export interface HealthDTO {
  status: string;
  database?: string;
  pgvector?: string;
  model_runtime?: string;
  mcp_boundary?: string;
  project?: string;
  environment?: string;
}

export interface ResearchExportDTO {
  schema_version: string;
  format: string;
  research_run: ResearchRunDetailDTO;
  claims: ClaimEvidenceDTO[];
  provenance: EvidenceTraceDTO[];
}

export interface BackgroundJobDTO {
  job_id: string;
  job_type: string;
  research_run_id?: string | null;
  status: string;
  attempts: number;
  max_attempts: number;
  result_payload?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface NotebookDTO {
  notebook_id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface NotebookCreateDTO {
  title: string;
  content: string;
}

export interface NotebookUpdateDTO {
  title?: string;
  content?: string;
}

export interface Message {
  id: string;
  role: DialogueRole;
  content: string;
  citations: Record<string, unknown>[];
  researchRunId?: string;
  timestamp: string;
}

export interface ResearchActivityItem {
  key: string;
  event: string;
  node?: string;
  status: string;
  summary: string;
}
