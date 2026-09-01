import { describe, expect, it } from 'vitest';
import { WORKSPACE_MODES, workspaceModeForView } from './modes';

describe('workspace mode contract', () => {
  it('publishes deterministic modes aligned with existing shell destinations', () => {
    expect(WORKSPACE_MODES.map((mode) => mode.id)).toEqual(['investigation', 'library', 'knowledge', 'system']);
    expect(WORKSPACE_MODES.map((mode) => mode.defaultPath)).toEqual(['/research', '/library/sources', '/memory', '/settings']);
    expect(new Set(WORKSPACE_MODES.flatMap((mode) => mode.views)).size).toBe(9);
  });

  it('derives the mode from the active route view and safely falls back to investigation', () => {
    expect(workspaceModeForView('inquiry').id).toBe('investigation');
    expect(workspaceModeForView('library').id).toBe('library');
    expect(workspaceModeForView('knowledge-graph').id).toBe('knowledge');
    expect(workspaceModeForView('settings').id).toBe('system');
  });
});
