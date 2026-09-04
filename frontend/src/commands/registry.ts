import { BookOpen, CircleHelp, FileSearch, FileText, MessageCircle, Network, NotebookPen, Settings, Share2, type LucideIcon } from 'lucide-react';
import { navigate } from '../routing';

export const COMMAND_PALETTE_SHORTCUT = 'Ctrl / Cmd K';

export function isCommandPaletteShortcut(event: Pick<KeyboardEvent, 'metaKey' | 'ctrlKey' | 'key'>): boolean {
  return (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
}

export interface CommandDefinition {
  id: string;
  label: string;
  keywords: string[];
  path: string;
  icon: LucideIcon;
  execute: () => void;
}

function routeCommand(id: string, label: string, path: string, icon: LucideIcon, keywords: string[] = []): CommandDefinition {
  return { id, label, keywords, path, icon, execute: () => navigate(path) };
}

export const COMMANDS: readonly CommandDefinition[] = [
  routeCommand('research', 'Research', '/research', CircleHelp, ['inquiry', 'question']),
  routeCommand('research-new', 'New research', '/research/new', CircleHelp, ['start', 'investigation']),
  routeCommand('research-runs', 'Research runs', '/research/runs', FileSearch, ['history', 'results']),
  routeCommand('research-questions', 'Questions', '/research/questions', CircleHelp, ['research questions']),
  routeCommand('library-sources', 'Sources', '/library/sources', FileText, ['library', 'reference']),
  routeCommand('library-documents', 'Documents', '/library/documents', BookOpen, ['library', 'files']),
  routeCommand('memory', 'Memory', '/memory', Network, ['understanding', 'epistemic']),
  routeCommand('knowledge-graph', 'Knowledge graph', '/knowledge-graph', Share2, ['provenance', 'relationships']),
  routeCommand('notebook', 'Notebook', '/notebook', NotebookPen, ['notes', 'writing']),
  routeCommand('dialogue', 'Dialogue', '/dialogue', MessageCircle, ['reflection', 'conversation']),
  routeCommand('settings', 'Settings', '/settings', Settings, ['configuration', 'health']),
];

export function filterCommands(query: string, commands: readonly CommandDefinition[] = COMMANDS): CommandDefinition[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [...commands];
  return commands.filter((command) => [command.id, command.label, ...command.keywords].some((value) => value.toLowerCase().includes(normalized)));
}
