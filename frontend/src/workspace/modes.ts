import type { AppView } from '../components/shell/AnvikshikiShell';

export type WorkspaceModeId = 'investigation' | 'library' | 'knowledge' | 'system';

export interface WorkspaceMode {
  id: WorkspaceModeId;
  label: string;
  description: string;
  defaultPath: string;
  views: readonly AppView[];
}

/**
 * Workspace modes are shell composition contexts, not backend research modes.
 * Their order is the stable order used by the mode switcher.
 */
export const WORKSPACE_MODES: readonly WorkspaceMode[] = [
  {
    id: 'investigation',
    label: 'Investigation',
    description: 'Research questions and runs',
    defaultPath: '/research',
    views: ['inquiry', 'history', 'questions'],
  },
  {
    id: 'library',
    label: 'Library',
    description: 'Sources and documents',
    defaultPath: '/library/sources',
    views: ['library'],
  },
  {
    id: 'knowledge',
    label: 'Knowledge',
    description: 'Memory, graph, notebook, and dialogue',
    defaultPath: '/memory',
    views: ['memory', 'knowledge-graph', 'notebook', 'dialogue'],
  },
  {
    id: 'system',
    label: 'System',
    description: 'Settings and runtime status',
    defaultPath: '/settings',
    views: ['settings'],
  },
];

export function workspaceModeForView(view: AppView): WorkspaceMode {
  return WORKSPACE_MODES.find((mode) => mode.views.includes(view)) ?? WORKSPACE_MODES[0];
}
