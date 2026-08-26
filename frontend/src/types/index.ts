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
  query: string;
  thread_id: string;
}

export interface ResearchEventNode {
  event: `${string}_event`;
  node: string;
  status: string;
  summary: string;
}

export interface ResearchEventCompleted {
  event: 'research_completed';
  validation_status: string;
  final_response: string;
  validated_claims_count: number;
}

export type ResearchEventDTO = ResearchEventStarted | ResearchEventNode | ResearchEventCompleted;

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
