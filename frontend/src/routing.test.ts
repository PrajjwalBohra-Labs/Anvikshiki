import { describe, expect, it } from 'vitest';
import { parseRoute, routeView } from './routing';

describe('application routing', () => {
  it('parses deep research and document URLs', () => {
    expect(parseRoute('/research/runs/run-42')).toEqual({ name: 'research-run', id: 'run-42' });
    expect(parseRoute('/library/documents/doc-7')).toEqual({ name: 'library-document', id: 'doc-7' });
    expect(parseRoute('/knowledge-graph/run-42')).toEqual({ name: 'knowledge-graph-run', id: 'run-42' });
    expect(parseRoute('/knowledge-graph/%E0%A4%A')).toEqual({ name: 'knowledge-graph-run', id: '%E0%A4%A' });
  });

  it('maps protected record routes to the correct shell section', () => {
    expect(routeView(parseRoute('/research/questions'))).toBe('questions');
    expect(routeView(parseRoute('/library/documents'))).toBe('library');
    expect(routeView(parseRoute('/knowledge-graph/run-42'))).toBe('knowledge-graph');
    expect(routeView(parseRoute('/unknown'))).toBe('inquiry');
  });
});
