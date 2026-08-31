import { describe, expect, it } from 'vitest';
import { parseRoute, routeView } from './routing';

describe('application routing', () => {
  it('parses deep research, document, and notebook URLs', () => {
    expect(parseRoute('/research/runs/run-42')).toEqual({ name: 'research-run', id: 'run-42' });
    expect(parseRoute('/library/documents/doc-7')).toEqual({ name: 'library-document', id: 'doc-7' });
    expect(parseRoute('/knowledge-graph/run-42')).toEqual({ name: 'knowledge-graph-run', id: 'run-42' });
    expect(parseRoute('/knowledge-graph/%E0%A4%A')).toEqual({ name: 'knowledge-graph-run', id: '%E0%A4%A' });
    expect(parseRoute('/notebook/notebook-42')).toEqual({ name: 'notebook-entry', id: 'notebook-42' });
  });

  it('maps protected record routes to the correct shell section', () => {
    expect(routeView(parseRoute('/research/questions'))).toBe('questions');
    expect(routeView(parseRoute('/library/documents'))).toBe('library');
    expect(routeView(parseRoute('/knowledge-graph/run-42'))).toBe('knowledge-graph');
    expect(routeView(parseRoute('/unknown'))).toBe('inquiry');
    expect(routeView(parseRoute('/notebook'))).toBe('notebook');
    expect(routeView(parseRoute('/notebook/notebook-42'))).toBe('notebook');
  });
});
