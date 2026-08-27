import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResearchRunDetailPage } from './ResearchRecords';

const api = vi.hoisted(() => ({ getResearchRun: vi.fn(), getRunClaims: vi.fn(), getRunAnalysis: vi.fn(), getRunProvenance: vi.fn(), getResearchQuestion: vi.fn() }));
vi.mock('../../api/services', () => api);

describe('research record rendering', () => {
  it('keeps claims and provenance visibly distinct', async () => {
    api.getResearchRun.mockResolvedValue({ run_id: 'run-1', research_question_id: null, query: 'Question', domain: 'Epistemology', status: 'completed', started_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:01:00Z', steps: [], result: { run_id: 'run-1', query: 'Question', validation_status: 'validated', final_response: 'Synthesis', validated_claims_count: 1, retrieved_passages: [], claims: [], specialist_analysis: { philosophical_arguments: [], source_criticisms: [], scientific_analyses: [], comparisons: [], challenges: [] }, validation: {} } });
    api.getRunClaims.mockResolvedValue([{ claim_id: 'claim-1', statement: 'A claim statement.', claim_type: 'MODEL_SYNTHESIS', confidence: 0.8, lifecycle_status: 'supported', evidence_links: [{ evidence_link_id: 'link-1', passage_id: 'passage-1', relation_type: 'SUPPORTS', confidence_weight: 0.9 }] }]);
    api.getRunAnalysis.mockResolvedValue({ philosophical_arguments: [], source_criticisms: [], scientific_analyses: [], comparisons: [], challenges: [] });
    api.getRunProvenance.mockResolvedValue([{ evidence_link_id: 'link-1', claim_id: 'claim-1', relation_type: 'SUPPORTS', confidence_weight: 0.9, passage: { passage_id: 'passage-1', document_id: 'doc-1', page_number: 4, content: 'Source passage text.', extraction_uncertainty: false, language: 'en' }, document: { document_id: 'doc-1', source_id: 'source-1', checksum_sha256: 'hash', mime_type: 'text/plain' }, source: { source_id: 'source-1', title: 'Source One', source_type: 'PRIMARY' }, source_lineage: [] }]);
    render(<ResearchRunDetailPage runId="run-1" />);
    await waitFor(() => expect(screen.getByText('A claim statement.')).toBeInTheDocument());
    expect(screen.getByText('Source passage text.')).toBeInTheDocument();
    expect(screen.getByText('Claims / Evidence relationships')).toBeInTheDocument();
    expect(screen.getByText('Provenance trace')).toBeInTheDocument();
  });
});
