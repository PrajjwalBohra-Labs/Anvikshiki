import { describe, expect, it, vi } from 'vitest';
import { COMMANDS, filterCommands, isCommandPaletteShortcut } from './registry';

vi.mock('../routing', () => ({ navigate: vi.fn() }));

describe('command registry', () => {
  it('publishes stable deterministic commands backed by existing routes', () => {
    expect(COMMANDS.map((command) => command.id)).toEqual([
      'research', 'research-new', 'research-runs', 'research-questions',
      'library-sources', 'library-documents', 'memory', 'knowledge-graph',
      'notebook', 'dialogue', 'settings',
    ]);
    expect(COMMANDS.every((command) => command.id.length > 0 && command.label.length > 0 && command.path.startsWith('/'))).toBe(true);
  });

  it('filters labels and keywords without changing registry order', () => {
    expect(filterCommands('notes').map((command) => command.id)).toEqual(['notebook']);
    expect(filterCommands('library').map((command) => command.id)).toEqual(['library-sources', 'library-documents']);
    expect(filterCommands('')).toEqual([...COMMANDS]);
  });

  it('recognizes the shared Ctrl/Cmd+K shortcut', () => {
    expect(isCommandPaletteShortcut({ ctrlKey: true, metaKey: false, key: 'k' })).toBe(true);
    expect(isCommandPaletteShortcut({ ctrlKey: false, metaKey: true, key: 'K' })).toBe(true);
    expect(isCommandPaletteShortcut({ ctrlKey: false, metaKey: false, key: 'k' })).toBe(false);
  });
});
