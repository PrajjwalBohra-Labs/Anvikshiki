import { useEffect, useState, type ReactNode } from 'react';
<<<<<<< HEAD
import { Activity, BookOpen, ChevronLeft, ChevronRight, CircleHelp, FileSearch, FileText, Library, LogOut, Menu, MessageCircle, Network, Search, Settings, X } from 'lucide-react';
import { navigate } from '../../routing';
import { CommandPalette } from '../command/CommandPalette';
=======
import { Activity, BookOpen, ChevronLeft, ChevronRight, CircleHelp, FileSearch, FileText, Library, LogOut, Menu, MessageCircle, Network, NotebookPen, Settings, Share2, X } from 'lucide-react';
import { Command } from 'lucide-react';
import { COMMAND_PALETTE_SHORTCUT } from '../../commands/registry';
import { navigate } from '../../routing';
import { WORKSPACE_MODES, workspaceModeForView, type WorkspaceModeId } from '../../workspace/modes';
>>>>>>> eb3e53806e8a5a05b49d42f5fe8100352a92335f
import './AnvikshikiShell.css';

export type AppView = 'inquiry' | 'history' | 'questions' | 'library' | 'memory' | 'knowledge-graph' | 'notebook' | 'dialogue' | 'settings';

interface NavItem { id: AppView; label: string; icon: typeof CircleHelp; path?: string; }
const navGroups: { mode: WorkspaceModeId; label: string; items: NavItem[] }[] = [
  { mode: 'investigation', label: 'Investigation', items: [
    { id: 'inquiry', label: 'Research', icon: CircleHelp },
    { id: 'history', label: 'Research runs', icon: FileSearch, path: '/research/runs' },
    { id: 'history', label: 'Background work', icon: Activity, path: '/research/jobs' },
    { id: 'questions', label: 'Questions', icon: CircleHelp },
  ] },
  { mode: 'library', label: 'Library', items: [
    { id: 'library', label: 'Library', icon: Library, path: '/library' },
    { id: 'library', label: 'Sources', icon: FileText, path: '/library/sources' },
    { id: 'library', label: 'Documents', icon: BookOpen, path: '/library/documents' },
  ] },
<<<<<<< HEAD
  { label: 'Knowledge', items: [
    { id: 'memory', label: 'Memory', icon: Network, path: '/memory' },
    { id: 'memory', label: 'Knowledge graph', icon: Network, path: '/knowledge-graph' },
    { id: 'inquiry', label: 'Notebook', icon: FileText, path: '/notebook' },
    { id: 'dialogue', label: 'Dialogue', icon: MessageCircle, path: '/dialogue' },
  ] },
  { label: 'System', items: [{ id: 'settings', label: 'Settings', icon: Settings, path: '/settings' }] },
=======
  { mode: 'knowledge', label: 'Knowledge', items: [
    { id: 'memory', label: 'Memory', icon: Network },
    { id: 'knowledge-graph', label: 'Knowledge graph', icon: Share2, path: '/knowledge-graph' },
    { id: 'notebook', label: 'Notebook', icon: NotebookPen, path: '/notebook' },
    { id: 'dialogue', label: 'Dialogue', icon: MessageCircle },
  ] },
  { mode: 'system', label: 'System', items: [{ id: 'settings', label: 'Settings', icon: Settings }] },
>>>>>>> eb3e53806e8a5a05b49d42f5fe8100352a92335f
];

interface Props {
  activeView: AppView;
  onViewChange: (view: AppView) => void;
  userName: string;
  onLogout: () => void;
  onOpenCommandPalette?: () => void;
  children: ReactNode;
}

export function AnvikshikiShell({ activeView, onViewChange, userName, onLogout, onOpenCommandPalette, children }: Props) {
  const [leftOpen, setLeftOpen] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
<<<<<<< HEAD
  const [paletteOpen, setPaletteOpen] = useState(false);
=======
  const activeMode = workspaceModeForView(activeView);
  const visibleNavGroups = navGroups.filter((group) => group.mode === activeMode.id);
  const selectMode = (modeId: WorkspaceModeId) => {
    const mode = WORKSPACE_MODES.find((candidate) => candidate.id === modeId);
    if (mode) navigate(mode.defaultPath);
  };
  const handleModeKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const offset = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? WORKSPACE_MODES.length - 1 : (index + offset + WORKSPACE_MODES.length) % WORKSPACE_MODES.length;
    selectMode(WORKSPACE_MODES[nextIndex].id);
  };
>>>>>>> eb3e53806e8a5a05b49d42f5fe8100352a92335f

  useEffect(() => { setMobileNavOpen(false); }, [activeView]);
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen(true); } if (event.key === 'Escape') setPaletteOpen(false); }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to research workspace</a>
      <header className="global-header">
        <button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNavOpen} aria-controls="primary-navigation" onClick={() => setMobileNavOpen(true)}><Menu size={18} /></button>
        <div className="header-title"><span className="eyebrow">Environment for inquiry</span><strong>ANVIKSHIKI</strong></div>
        <div className="header-context"><span className="header-rule" aria-hidden="true" /><span>Private intellectual workstation</span></div>
        <div className="header-status"><span className="status-dot" aria-hidden="true" /><span>LOCAL SESSION</span></div>
        <button className="icon-button palette-trigger" aria-label="Open command palette" onClick={() => setPaletteOpen(true)}><Search size={16} /><span>Ctrl+K</span></button>
      </header>

      {mobileNavOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <div className="shell-body">
        <aside className={"left-sidebar " + (leftOpen ? 'is-open ' : 'is-collapsed ') + (mobileNavOpen ? 'mobile-open' : '')}>
          <div className="brand-lockup">
            <div className="brand-mark"><img src="/anvikshiki-logo.png" alt="" /></div>
            {leftOpen && <div><strong>ANVIKSHIKI</strong><span>Research instrument</span></div>}
            <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={17} /></button>
          </div>
          {onOpenCommandPalette && <button className="command-trigger" type="button" onClick={onOpenCommandPalette} aria-label="Open command palette" aria-haspopup="dialog" title="Open command palette"><Command size={15} />{leftOpen && <><span>Command palette</span><kbd>{COMMAND_PALETTE_SHORTCUT}</kbd></>}</button>}
          <div className="workspace-mode-selector" role="tablist" aria-label="Workspace modes">
            {WORKSPACE_MODES.map((mode, index) => (
              <button
                key={mode.id}
                id={`workspace-mode-${mode.id}`}
                className={"workspace-mode-tab " + (mode.id === activeMode.id ? 'active' : '')}
                type="button"
                role="tab"
                aria-selected={mode.id === activeMode.id}
                aria-controls="primary-navigation"
                aria-label={`${mode.label}: ${mode.description}`}
                tabIndex={mode.id === activeMode.id ? 0 : -1}
                title={`${mode.label}: ${mode.description}`}
                onClick={() => selectMode(mode.id)}
                onKeyDown={(event) => handleModeKeyDown(event, index)}
              >
                <span aria-hidden="true">{mode.label.slice(0, 1)}</span>
                {leftOpen && <span>{mode.label}</span>}
              </button>
            ))}
          </div>
          <nav id="primary-navigation" aria-label="Primary navigation" className="primary-nav">
            {visibleNavGroups.map((group) => <div className="nav-group" key={group.label}>
              {leftOpen && <span className="nav-group-label">{group.label}</span>}
              {group.items.map(({ id, label, icon: Icon, path }) => {
                const pathActive = path ? (window.location.pathname === path || window.location.pathname.startsWith(`${path}/`)) : true;
                const isActive = activeView === id && pathActive;
                return <button key={`${id}-${label}`} className={"nav-item " + (isActive ? 'active' : '')} onClick={() => path ? navigate(path) : onViewChange(id)} aria-current={isActive ? 'page' : undefined}>
                  <Icon size={16} />{leftOpen && <span>{label}</span>}
                </button>;
              })}
            </div>)}
          </nav>
          {leftOpen && <div className="sidebar-context"><span className="eyebrow">Current investigation</span><p>No investigation selected.</p><span className="muted-copy">Start with a question to establish a research context.</span></div>}
          <div className="sidebar-footer">
            {leftOpen && <span className="user-id" title={userName}>{userName}</span>}
            {leftOpen && <button className="icon-button" aria-label="Log out" onClick={onLogout}><LogOut size={15} /></button>}
            <button className="icon-button" aria-label={leftOpen ? 'Collapse navigation' : 'Expand navigation'} onClick={() => setLeftOpen((value) => !value)}>
              {leftOpen ? <ChevronLeft size={17} /> : <ChevronRight size={17} />}
            </button>
          </div>
        </aside>
        <main id="main-content" className="main-region">{children}</main>
      </div>
      <footer className="status-bar">
        <span><Activity size={13} /> {activeView === 'inquiry' ? 'RESEARCH READY' : activeView.toUpperCase()}</span>
        <span><FileText size={13} /> Evidence appears when returned by the backend</span>
        <span className="status-bar-right"><BookOpen size={13} /> Local-first workspace</span>
      </footer>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
