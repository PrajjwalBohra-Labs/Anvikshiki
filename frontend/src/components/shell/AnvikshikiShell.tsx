import { useEffect, useState, type ReactNode } from 'react';
import { Activity, BookOpen, ChevronLeft, ChevronRight, CircleHelp, FileSearch, FileText, Library, LogOut, Menu, MessageCircle, Network, NotebookPen, Settings, Share2, X } from 'lucide-react';
import { navigate } from '../../routing';
import './AnvikshikiShell.css';

export type AppView = 'inquiry' | 'history' | 'questions' | 'library' | 'memory' | 'knowledge-graph' | 'notebook' | 'dialogue' | 'settings';

interface NavItem { id: AppView; label: string; icon: typeof CircleHelp; path?: string; }
const navGroups: { label: string; items: NavItem[] }[] = [
  { label: 'Investigation', items: [
    { id: 'inquiry', label: 'Research', icon: CircleHelp },
    { id: 'history', label: 'Research runs', icon: FileSearch },
    { id: 'questions', label: 'Questions', icon: CircleHelp },
  ] },
  { label: 'Library', items: [
    { id: 'library', label: 'Library', icon: Library, path: '/library' },
    { id: 'library', label: 'Sources', icon: FileText, path: '/library/sources' },
    { id: 'library', label: 'Documents', icon: BookOpen, path: '/library/documents' },
  ] },
  { label: 'Knowledge', items: [
    { id: 'memory', label: 'Memory', icon: Network },
    { id: 'knowledge-graph', label: 'Knowledge graph', icon: Share2, path: '/knowledge-graph' },
    { id: 'notebook', label: 'Notebook', icon: NotebookPen, path: '/notebook' },
    { id: 'dialogue', label: 'Dialogue', icon: MessageCircle },
  ] },
  { label: 'System', items: [{ id: 'settings', label: 'Settings', icon: Settings }] },
];

interface Props {
  activeView: AppView;
  onViewChange: (view: AppView) => void;
  userName: string;
  onLogout: () => void;
  children: ReactNode;
}

export function AnvikshikiShell({ activeView, onViewChange, userName, onLogout, children }: Props) {
  const [leftOpen, setLeftOpen] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => { setMobileNavOpen(false); }, [activeView]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to research workspace</a>
      <header className="global-header">
        <button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNavOpen} aria-controls="primary-navigation" onClick={() => setMobileNavOpen(true)}><Menu size={18} /></button>
        <div className="header-title"><span className="eyebrow">Environment for inquiry</span><strong>ANVIKSHIKI</strong></div>
        <div className="header-context"><span className="header-rule" aria-hidden="true" /><span>Private intellectual workstation</span></div>
        <div className="header-status"><span className="status-dot" aria-hidden="true" /><span>LOCAL SESSION</span></div>
      </header>

      {mobileNavOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <div className="shell-body">
        <aside className={"left-sidebar " + (leftOpen ? 'is-open ' : 'is-collapsed ') + (mobileNavOpen ? 'mobile-open' : '')}>
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">A</div>
            {leftOpen && <div><strong>ANVIKSHIKI</strong><span>Research instrument</span></div>}
            <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={17} /></button>
          </div>
          <nav id="primary-navigation" aria-label="Primary navigation" className="primary-nav">
            {navGroups.map((group) => <div className="nav-group" key={group.label}>
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
    </div>
  );
}
