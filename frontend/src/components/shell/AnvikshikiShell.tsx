import { useEffect, useState, type ReactNode } from 'react';
import { Activity, BookOpen, ChevronLeft, ChevronRight, CircleHelp, FileSearch, FileText, Library, LogOut, Menu, Network, Settings, Sparkles, X } from 'lucide-react';
import './AnvikshikiShell.css';

export type AppView = 'inquiry' | 'history' | 'questions' | 'library' | 'memory' | 'settings';

interface NavItem { id: AppView; label: string; icon: typeof CircleHelp; }
const navItems: NavItem[] = [
  { id: 'inquiry', label: 'Inquiry', icon: CircleHelp },
  { id: 'history', label: 'Research history', icon: FileSearch },
  { id: 'questions', label: 'Questions', icon: CircleHelp },
  { id: 'library', label: 'Library', icon: Library },
  { id: 'memory', label: 'Understanding', icon: Network },
  { id: 'settings', label: 'Settings', icon: Settings },
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
      <header className="global-header">
        <button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNavOpen} aria-controls="primary-navigation" onClick={() => setMobileNavOpen(true)}><Menu size={18} /></button>
        <div className="header-title"><span className="eyebrow">Environment for inquiry</span><strong>Anvīkṣikī</strong></div>
        <div className="header-search" aria-label="Global search is not yet available"><Sparkles size={15} /><span>Research workspace</span><kbd>⌘K</kbd></div>
        <div className="header-status"><span className="status-dot" aria-hidden="true" /><span>Local system</span></div>
      </header>

      {mobileNavOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <div className="shell-body">
        <aside className={"left-sidebar " + (leftOpen ? 'is-open ' : 'is-collapsed ') + (mobileNavOpen ? 'mobile-open' : '')}>
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">A</div>
            {leftOpen && <div><strong>ANVĪKṢIKĪ</strong><span>Research instrument</span></div>}
            <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={17} /></button>
          </div>
          <nav id="primary-navigation" aria-label="Primary navigation" className="primary-nav">
            {navItems.map(({ id, label, icon: Icon }) => (
              <button key={id} className={"nav-item " + (activeView === id ? 'active' : '')} onClick={() => onViewChange(id)} aria-current={activeView === id ? 'page' : undefined}>
                <Icon size={17} />{leftOpen && <span>{label}</span>}
              </button>
            ))}
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
        <main className="main-region">{children}</main>
      </div>
      <footer className="status-bar">
        <span><Activity size={13} /> {activeView === 'inquiry' ? 'RESEARCH READY' : activeView.toUpperCase()}</span>
        <span><FileText size={13} /> Evidence appears when returned by the backend</span>
        <span className="status-bar-right"><BookOpen size={13} /> Local-first workspace</span>
      </footer>
    </div>
  );
}
