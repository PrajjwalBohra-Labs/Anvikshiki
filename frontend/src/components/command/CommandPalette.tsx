import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Search, X } from 'lucide-react';
import { navigate } from '../../routing';
import './CommandPalette.css';

interface Command { id: string; label: string; keywords: string; path: string; }
const commands: Command[] = [
  { id: 'research', label: 'Begin an investigation', keywords: 'research inquiry question', path: '/research' },
  { id: 'runs', label: 'Review research runs', keywords: 'history records results', path: '/research/runs' },
  { id: 'sources', label: 'Open source library', keywords: 'library sources documents', path: '/library/sources' },
  { id: 'memory', label: 'Open understanding memory', keywords: 'memory epistemic positions', path: '/memory' },
  { id: 'graph', label: 'Explore knowledge graph', keywords: 'provenance relationships graph', path: '/knowledge-graph' },
  { id: 'notebook', label: 'Open notebook surface', keywords: 'notes writing notebook', path: '/notebook' },
  { id: 'settings', label: 'Open workspace settings', keywords: 'settings health runtime', path: '/settings' },
];

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState(''); const [index, setIndex] = useState(0); const inputRef = useRef<HTMLInputElement>(null);
  const visible = commands.filter((command) => `${command.label} ${command.keywords}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => a.label.localeCompare(b.label));
  useEffect(() => { if (open) { setQuery(''); setIndex(0); window.setTimeout(() => inputRef.current?.focus(), 0); } }, [open]);
  useEffect(() => { if (index >= visible.length) setIndex(Math.max(0, visible.length - 1)); }, [index, visible.length]);
  if (!open) return null;
  const execute = (command: Command | undefined) => { if (!command) return; onClose(); navigate(command.path); };
  return <div className="palette-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="command-palette" role="dialog" aria-modal="true" aria-labelledby="command-palette-title"><div className="palette-heading"><span id="command-palette-title" className="eyebrow">Inquiry commands</span><button className="icon-button" aria-label="Close command palette" onClick={onClose}><X size={16} /></button></div><div className="palette-search"><Search size={16} aria-hidden="true" /><input ref={inputRef} role="combobox" aria-label="Search commands" aria-controls="command-list" aria-activedescendant={visible[index] ? `command-${visible[index].id}` : undefined} value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'ArrowDown') { event.preventDefault(); setIndex((value) => Math.min(value + 1, Math.max(0, visible.length - 1))); } if (event.key === 'ArrowUp') { event.preventDefault(); setIndex((value) => Math.max(value - 1, 0)); } if (event.key === 'Enter') execute(visible[index]); if (event.key === 'Escape') onClose(); }} placeholder="Find an action..." /></div>{visible.length === 0 ? <p className="palette-empty" role="status">No commands match this inquiry.</p> : <ul id="command-list" className="command-list" role="listbox">{visible.map((command, commandIndex) => <li key={command.id}><button id={`command-${command.id}`} type="button" role="option" aria-selected={commandIndex === index} onMouseEnter={() => setIndex(commandIndex)} onClick={() => execute(command)}><span>{command.label}<small>{command.keywords}</small></span><ArrowRight size={14} /></button></li>)}</ul>}<div className="palette-hint">Up / Down / Enter open / Esc close</div></section></div>;
}
