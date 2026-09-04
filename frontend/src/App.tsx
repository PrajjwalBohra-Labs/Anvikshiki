import { useEffect, useState, type FormEvent } from 'react';
import { AlertTriangle, Database, HeartPulse, LoaderCircle, MessageCircle, ShieldCheck } from 'lucide-react';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { AuthScreen } from './components/auth/AuthScreen';
import { DocumentsPage, DocumentDetailPage, SourcesPage, WebAcquisitionPanel } from './components/library/LibraryPages';
import { ResearchHistoryPage, ResearchQuestionsPage, ResearchRunDetailPage } from './components/research/ResearchRecords';
import { ResearchWorkspace } from './components/research/ResearchWorkspace';
import { KnowledgeGraphPage } from './components/knowledge/KnowledgeGraphPage';
import { BackgroundJobsPage } from './components/jobs/BackgroundJobsPage';
import { AnvikshikiShell, type AppView } from './components/shell/AnvikshikiShell';
import { MemoryPage } from './components/memory/MemoryPage';
import { NotebookPage } from './components/notebook/NotebookPage';
import { CommandPalette } from './components/commands/CommandPalette';
import { COMMANDS, isCommandPaletteShortcut } from './commands/registry';
import { executeDialogue, exportResearchRun, getHealth } from './api/services';
import { navigate, routeView, useRoute } from './routing';
import type { DialogueTurnDTO, HealthDTO } from './types';
import './styles/tokens.css';
import './styles/app.css';

function LoadingMessage({ label }: { label: string }) { return <p className="muted-copy loading-message" role="status"><LoaderCircle className="spin" size={14} /> {label}</p>; }
function ErrorMessage({ message }: { message: string }) { return <div className="inline-error" role="alert"><AlertTriangle size={15} />{message}</div>; }

function ExportRecordAction({ runId }: { runId: string }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const exportRecord = async () => { setBusy(true); setError(''); try { const data = await exportResearchRun(runId); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const anchor = window.document.createElement('a'); anchor.href = url; anchor.download = `research-${runId}.json`; anchor.click(); URL.revokeObjectURL(url); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Research export failed.'); } finally { setBusy(false); } };
  return <div className="record-export"><button className="button button-primary" type="button" onClick={() => void exportRecord()} disabled={busy}>{busy ? 'Preparing export...' : 'Export this research record'}</button>{error && <ErrorMessage message={error} />}</div>;
}
function DialoguePage() {
  const [input, setInput] = useState(''); const [mode, setMode] = useState('socratic'); const [turn, setTurn] = useState<DialogueTurnDTO | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  const submit = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!input.trim()) return; setLoading(true); setError(''); try { setTurn(await executeDialogue(input.trim(), mode)); setInput(''); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Dialogue response failed.'); } finally { setLoading(false); } };
  return <section className="secondary-page dialogue-page"><div className="eyebrow">Knowledge / Dialogue</div><div className="dialogue-hero"><div><h1>Think against<br /><em>your first answer.</em></h1><p className="page-lede">A reflective turn is separate from a research run. Choose a mode, offer a thought, and let the backend return the next pressure point.</p></div><div className="dialogue-index" aria-hidden="true">D<br />/04</div></div><section className={`dialogue-panel panel dialogue-mode-${mode}`}><div className="panel-heading"><span className="eyebrow">Conversation desk</span><span className="muted-copy">No conversation state is fabricated</span></div><form className="dialogue-form" onSubmit={submit}><label htmlFor="dialogue-mode" className="sr-only">Dialogue mode</label><select id="dialogue-mode" value={mode} onChange={(event) => setMode(event.target.value)} disabled={loading}><option value="socratic">Socratic</option><option value="challenge">Challenge</option><option value="explanation">Explanation</option><option value="counterexample">Counterexample</option><option value="debate">Debate</option><option value="reflective">Reflective</option></select><label htmlFor="dialogue-input" className="sr-only">Dialogue prompt</label><input id="dialogue-input" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask for a challenge, clarification, or counterexample..." disabled={loading} /><button className="button button-primary" type="submit" disabled={loading || !input.trim()}>{loading ? <LoaderCircle className="spin" size={14} /> : <MessageCircle size={14} />} Send</button></form>{error && <ErrorMessage message={error} />}{turn && <article className="dialogue-response"><div className="eyebrow">{turn.dialogue_mode} response{turn.source_title ? `  /  ${turn.source_title}` : ''}</div><p>{turn.response_text}</p><div className="dialogue-flags"><span>{turn.evidence_linked ? 'Evidence linked' : 'No evidence linked'}</span><span>{turn.preserves_uncertainty ? 'Uncertainty preserved' : 'Uncertainty not reported'}</span>{turn.disagrees_with_user && <span>Challenges the premise</span>}</div></article>}</section></section>;
}

function SettingsPage({ user }: { user: { user_id: string; username: string } }) {
  const [health, setHealth] = useState<HealthDTO | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  useEffect(() => { let active = true; void getHealth().then((value) => { if (active) setHealth(value); }).catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Health status could not be loaded.'); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  return <section className="secondary-page"><div className="eyebrow">Settings / Runtime</div><h1>Workspace settings</h1><p className="page-lede">Only frontend-safe identity and runtime information is shown. Server secrets remain outside the client.</p><div className="settings-grid"><div className="settings-field"><span className="eyebrow">Authenticated identity</span><strong>{user.username}</strong><small>User ID {user.user_id}</small><small>Bearer session is managed centrally for protected requests.</small></div><div className="health-card"><div className="panel-heading"><span className="eyebrow">System health</span><HeartPulse size={16} /></div>{loading && <LoadingMessage label="Checking backend health..." />}{error && <ErrorMessage message={error} />}{health && <div className="health-list"><HealthRow icon={<Database size={14} />} label="Database" value={health.database || health.status} /><HealthRow icon={<Database size={14} />} label="pgvector" value={health.pgvector || 'Not reported'} /><HealthRow icon={<ShieldCheck size={14} />} label="MCP boundary" value={health.mcp_boundary || 'Not reported'} /></div>}</div></div></section>;
}

function HealthRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="health-row">{icon}<span>{label}</span><strong>{value}</strong></div>; }

function AuthenticatedApp() {
  const { user, initializing, logout } = useAuth(); const route = useRoute();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isCommandPaletteShortcut(event)) {
        event.preventDefault();
        setCommandPaletteOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
  if (initializing) return <main className="auth-screen"><div className="auth-restore"><img src="/anvikshiki-logo.png" alt="" /><LoadingMessage label="Restoring local research session..." /></div></main>;
  if (!user) return <AuthScreen />;
  const activeView: AppView = routeView(route);
  const changeView = (view: AppView) => navigate(view === 'inquiry' ? '/research' : view === 'history' ? '/research/runs' : view === 'questions' ? '/research/questions' : view === 'library' ? '/library/sources' : `/${view}`);
  let content: React.ReactNode;
  switch (route.name) {
    case 'research-run': content = <><ResearchRunDetailPage runId={route.id} /><ExportRecordAction runId={route.id} /></>; break;
    case 'research-runs': content = <ResearchHistoryPage />; break;
    case 'research-questions': content = <ResearchQuestionsPage />; break;
    case 'research-jobs': content = <BackgroundJobsPage />; break;
    case 'library-document': content = <DocumentDetailPage documentId={route.id} />; break;
    case 'library-documents': content = <DocumentsPage />; break;
    case 'library-sources': content = <><SourcesPage /><section className="secondary-page secondary-page-compact"><WebAcquisitionPanel /></section></>; break;
    case 'library': content = <SourcesPage />; break;
    case 'memory': content = <MemoryPage userId={user.user_id} />; break;
    case 'knowledge-graph': content = <KnowledgeGraphPage />; break;
    case 'knowledge-graph-run': content = <KnowledgeGraphPage runId={route.id} />; break;
    case 'notebook': content = <NotebookPage />; break;
    case 'notebook-entry': content = <NotebookPage notebookId={route.id} />; break;
    case 'dialogue': content = <DialoguePage />; break;
    case 'settings': content = <SettingsPage user={user} />; break;
    case 'not-found': content = <section className="secondary-page"><div className="eyebrow">404 / Not found</div><h1>This path is not part of the instrument.</h1><button className="button button-primary" type="button" onClick={() => navigate('/research')}>Return to inquiry</button></section>; break;
    default: content = <ResearchWorkspace userId={user.user_id} />;
  }
  return <><AnvikshikiShell activeView={activeView} onViewChange={changeView} userName={user.username} onLogout={() => { void logout(); }} onOpenCommandPalette={() => setCommandPaletteOpen(true)}><div key={window.location.pathname}>{content}</div></AnvikshikiShell><CommandPalette isOpen={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} commands={COMMANDS} /></>;
}

export function App() { return <AuthProvider><AuthenticatedApp /></AuthProvider>; }
export default App;
