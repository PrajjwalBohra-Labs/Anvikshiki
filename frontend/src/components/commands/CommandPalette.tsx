import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Command, CornerDownLeft, Search } from 'lucide-react';
import { COMMANDS, filterCommands, type CommandDefinition } from '../../commands/registry';
import './CommandPalette.css';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  commands?: readonly CommandDefinition[];
}

export function CommandPalette({ isOpen, onClose, commands = COMMANDS }: Props) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const listId = useId();
  const filtered = useMemo(() => filterCommands(query, commands), [commands, query]);

  useEffect(() => {
    if (!isOpen) return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery('');
    setSelectedIndex(0);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(focusTimer);
      previousFocus.current?.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (selectedIndex >= filtered.length) setSelectedIndex(Math.max(0, filtered.length - 1));
  }, [filtered.length, selectedIndex]);

  if (!isOpen) return null;

  const executeSelected = () => {
    const command = filtered[selectedIndex];
    if (!command) return;
    command.execute();
    onClose();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setSelectedIndex((index) => filtered.length ? (index + 1) % filtered.length : 0); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setSelectedIndex((index) => filtered.length ? (index - 1 + filtered.length) % filtered.length : 0); }
    else if (event.key === 'Home') { event.preventDefault(); setSelectedIndex(0); }
    else if (event.key === 'End') { event.preventDefault(); setSelectedIndex(Math.max(0, filtered.length - 1)); }
    else if (event.key === 'Enter') { event.preventDefault(); executeSelected(); }
    else if (event.key === 'Escape') { event.preventDefault(); onClose(); }
  };

  return <div className="command-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="command-dialog" role="dialog" aria-modal="true" aria-labelledby={`${listId}-title`}>
      <h2 id={`${listId}-title`} className="sr-only">Command palette</h2>
      <div className="command-input-row"><Command size={16} aria-hidden="true" /><label className="sr-only" htmlFor={`${listId}-input`}>Search commands</label><input id={`${listId}-input`} ref={inputRef} className="command-input" value={query} onChange={(event) => { setQuery(event.target.value); setSelectedIndex(0); }} onKeyDown={handleKeyDown} role="combobox" aria-expanded="true" aria-controls={`${listId}-list`} aria-activedescendant={filtered[selectedIndex] ? `${listId}-${filtered[selectedIndex].id}` : undefined} placeholder="Search commands…" autoComplete="off" /><kbd>ESC</kbd></div>
      <div id={`${listId}-list`} className="command-results" role="listbox" aria-label="Available commands">
        {filtered.length === 0 && <p className="command-empty" role="status">No matching commands.</p>}
        {filtered.map((command, index) => { const Icon = command.icon; return <button id={`${listId}-${command.id}`} key={command.id} className={`command-option${index === selectedIndex ? ' is-selected' : ''}`} type="button" role="option" aria-selected={index === selectedIndex} onMouseEnter={() => setSelectedIndex(index)} onClick={() => { command.execute(); onClose(); }}><Icon size={15} aria-hidden="true" /><span>{command.label}</span>{index === selectedIndex && <CornerDownLeft className="command-enter" size={13} aria-hidden="true" />}</button>; })}
      </div>
      <p className="command-help"><Search size={12} aria-hidden="true" /> Type to filter <span>↑↓</span> Navigate <span>↵</span> Open <span>Esc</span> Close</p>
    </section>
  </div>;
}
