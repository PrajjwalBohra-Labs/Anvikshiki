export type SourceType = 'PRIMARY' | 'TRANSLATION' | 'COMMENTARY' | 'CRITICISM' | 'SECONDARY' | 'UNVERIFIED';

export type EpistemicStatus = 'tentative' | 'accepted' | 'rejected' | 'contested' | 'under investigation' | 'unresolved';

export interface Citation {
  passageId: string;
  sourceTitle: string;
  pageNumber?: number;
  extractedText: string;
}

export interface DialogueMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[];
  researchRunId?: string;
  timestamp: string;
}

export interface ResearchInvestigation {
  id: string;
  mainQuestion: string;
  subquestions: string[];
  scope?: string;
  domain?: string;
  status: string;
  establishedFindings: string[];
  unresolvedQuestions: string[];
  suggestedNextStep?: string;
}

export interface CognitiveObservation {
  id: string;
  observationType: string;
  observationDetail: string;
  evidenceReference: string;
  confidence: number;
  timestamp: string;
}