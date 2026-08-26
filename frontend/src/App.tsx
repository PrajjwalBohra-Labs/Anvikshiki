import { useEffect, useState } from 'react';
import { AlertTriangle, Database, ExternalLink, FileText, HeartPulse, LoaderCircle, ShieldCheck, Upload } from 'lucide-react';
import { AnvikshikiShell, type AppView } from './components/shell/AnvikshikiShell';
import { ResearchWorkspace } from './components/research/ResearchWorkspace';
import { createSource, getDocumentPassages, getEpistemicPositions, getHealth, listSources, uploadDocument } from './api/services';
import type { DocumentUploadResponseDTO, EpistemicPositionDTO, HealthDTO, PassageDTO, SourceDTO, SourceType } from './types';
import './styles/app.css';

const USER_STORAGE_KEY = 'anvikshiki.user-id';

function initialUserId(): string {
  return import.meta.env.VITE_ANVIKSHIKI_USER_ID || window.localStorage.getItem(USER_STORAGE_KEY) || '';
}

function LoadingMessage({ label }: { label: string }) {
  return <p className="muted-copy loading-message">{label}</p>;
}

function ErrorMessage({ message }: { message: string }) {
  return <div className="inline-error" role="alert"><AlertTriangle size={15} />{message}</div>;
}

function safeExternalUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null;
  } catch {
    return null;
  }
}

function LibraryView() {
  const [sources, setSources] = useState<SourceDTO[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceAuthor, setSourceAuthor] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('UNVERIFIED');
  const [sourceUrl, setSourceUrl] = useState('');
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [libraryMessage, setLibraryMessage] = useState('');
  const [uploadedDocument, setUploadedDocument] = useState<DocumentUploadResponseDTO | null>(null);
  const [passages, setPassages] = useState<PassageDTO[]>([]);

  useEffect(() => {
    let active = true;
    listSources().then((value) => { if (active) setSources(value); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Sources could not be loaded.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const refreshSources = async () => {
    const value = await listSources();
    setSources(value);
    if (!selectedSourceId && value[0]) setSelectedSourceId(value[0].id);
  };

  const createNewSource = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sourceTitle.trim()) return;
    setLibraryBusy(true);
    setError('');
    setLibraryMessage('');
    try {
      const source = await createSource({
        title: sourceTitle.trim(),
        author: sourceAuthor.trim() || null,
        source_type: sourceType,
        reference_url: sourceUrl.trim() || null,
      });
      setSourceTitle('');
      setSourceAuthor('');
      setSourceUrl('');
      await refreshSources();
      setSelectedSourceId(source.id);
      setLibraryMessage('Source created. It can now receive a document upload.');
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Source could not be created.');
    } finally {
      setLibraryBusy(false);
    }
  };

  const uploadToSource = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSourceId || !file) return;
    setLibraryBusy(true);
    setError('');
    setLibraryMessage('');
    setUploadedDocument(null);
    setPassages([]);
    try {
      const uploaded = await uploadDocument(selectedSourceId, file);
      setUploadedDocument(uploaded);
      setFile(null);
      setLibraryMessage('Document ingested successfully.');
      setPassages(await getDocumentPassages(uploaded.document_id));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Document could not be ingested.');
    } finally {
      setLibraryBusy(false);
    }
  };

  return (
    <section className="secondary-page">
      <div className="eyebrow">Library / Sources</div>
      <h1>Source library</h1>
      <p className="page-lede">Indexed sources returned by the research backend.</p>
      <div className="library-actions">
        <form className="library-card" onSubmit={createNewSource}>
          <div className="panel-heading"><span className="eyebrow">Register source</span><FileText size={16} /></div>
          <div className="library-form-grid">
            <label><span className="eyebrow">Title</span><input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} required /></label>
            <label><span className="eyebrow">Author</span><input value={sourceAuthor} onChange={(event) => setSourceAuthor(event.target.value)} /></label>
            <label><span className="eyebrow">Source type</span><select value={sourceType} onChange={(event) => setSourceType(event.target.value as SourceType)}><option value="PRIMARY">Primary</option><option value="SECONDARY">Secondary</option><option value="TRANSLATION">Translation</option><option value="COMMENTARY">Commentary</option><option value="DISCOVERY_ONLY">Discovery only</option><option value="UNVERIFIED">Unverified</option></select></label>
            <label><span className="eyebrow">Reference URL</span><input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." /></label>
          </div>
          <button className="button button-primary" type="submit" disabled={libraryBusy || !sourceTitle.trim()}>Register source</button>
        </form>
        <form className="library-card" onSubmit={uploadToSource}>
          <div className="panel-heading"><span className="eyebrow">Ingest document</span><Upload size={16} /></div>
          <div className="library-form-grid upload-grid">
            <label><span className="eyebrow">Existing source</span><select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)} disabled={sources.length === 0}><option value="">Select a source</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.title}</option>)}</select></label>
            <label><span className="eyebrow">File</span><input type="file" accept=".pdf,.txt,.md,.markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          </div>
          <button className="button button-primary" type="submit" disabled={libraryBusy || !selectedSourceId || !file}>{libraryBusy ? <LoaderCircle className="spin" size={14} /> : <Upload size={14} />} Ingest document</button>
          <small className="muted-copy">The backend accepts the file and source ID; document parsing is performed server-side.</small>
        </form>
      </div>
      {libraryMessage && <div className="success-callout" role="status">{libraryMessage}</div>}
      {loading && <LoadingMessage label="Loading sources..." />}
      {error && <ErrorMessage message={error} />}
      {!loading && !error && sources.length === 0 && <div className="empty-card"><FileText size={18} /><span>No sources are currently returned by the backend.</span></div>}
      <div className="source-list">
        {sources.map((source) => (
          <article className="source-card" key={source.id}>
            <div><span className="eyebrow">{source.source_type}</span><h2>{source.title}</h2><p>{source.author || 'Author not provided'}{source.original_language ? ' · ' + source.original_language : ''}</p></div>
            {safeExternalUrl(source.reference_url) && <a href={safeExternalUrl(source.reference_url) ?? undefined} target="_blank" rel="noreferrer" aria-label={'Open ' + source.title}><ExternalLink size={15} /></a>}
          </article>
        ))}
      </div>
      {uploadedDocument && <section className="uploaded-document panel"><div className="panel-heading"><span className="eyebrow">Latest ingestion</span><span className="muted-copy">{uploadedDocument.mime_type}</span></div><div className="upload-summary"><span>Document {uploadedDocument.document_id.slice(0, 8)}…</span><span>{uploadedDocument.passages_count} passages</span><span>{uploadedDocument.total_pages ? uploadedDocument.total_pages + ' pages' : 'Pages not reported'}</span></div>{passages.length > 0 && <details><summary>Inspect extracted passages</summary><div className="passage-list">{passages.slice(0, 20).map((passage) => <article key={passage.id}><span className="eyebrow">{passage.page_number ? 'Page ' + passage.page_number : 'Page not reported'} · {passage.language}</span><p>{passage.content}</p>{passage.extraction_uncertainty && <small className="uncertainty-note">Extraction uncertainty reported by backend</small>}</article>)}</div></details>}</section>}
    </section>
  );
}

function MemoryView({ userId }: { userId: string }) {
  const [positions, setPositions] = useState<EpistemicPositionDTO[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(Boolean(userId));

  useEffect(() => {
    if (!userId) { setLoading(false); return; }
    let active = true;
    setLoading(true);
    getEpistemicPositions(userId).then((value) => { if (active) setPositions(value); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Understanding state could not be loaded.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId]);

  return (
    <section className="secondary-page">
      <div className="eyebrow">Understanding / Epistemic memory</div>
      <h1>Current understanding</h1>
      <p className="page-lede">Only persisted positions returned by the backend appear here.</p>
      {!userId && <div className="empty-card"><ShieldCheck size={18} /><span>Configure a backend user ID in Settings to inspect positions.</span></div>}
      {loading && <LoadingMessage label="Loading epistemic positions..." />}
      {error && <ErrorMessage message={error} />}
      {!loading && !error && userId && positions.length === 0 && <div className="empty-card"><ShieldCheck size={18} /><span>No epistemic positions are currently returned for this user.</span></div>}
      <div className="position-list">
        {positions.map((position) => (
          <article className="position-card" key={position.position_id}>
            <div className="position-heading"><span className="eyebrow">{position.status}</span><span>{Math.round(position.confidence * 100)}% confidence</span></div>
            <p>{position.claim_statement}</p>
            <small>{position.position}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function SettingsView({ userId, onUserIdChange }: { userId: string; onUserIdChange: (value: string) => void }) {
  const [health, setHealth] = useState<HealthDTO | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getHealth().then((value) => { if (active) setHealth(value); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Health status could not be loaded.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const saveUserId = (value: string) => {
    onUserIdChange(value);
    if (value) window.localStorage.setItem(USER_STORAGE_KEY, value);
    else window.localStorage.removeItem(USER_STORAGE_KEY);
  };

  return (
    <section className="secondary-page">
      <div className="eyebrow">Settings / Runtime</div>
      <h1>Workspace settings</h1>
      <p className="page-lede">Only frontend-safe configuration is shown. Server secrets remain outside the client.</p>
      <div className="settings-grid">
        <label className="settings-field"><span className="eyebrow">Backend user ID</span><input value={userId} onChange={(event) => saveUserId(event.target.value.trim())} placeholder="Existing backend user ID" /><small>This must already exist in the backend database.</small></label>
        <div className="health-card"><div className="panel-heading"><span className="eyebrow">System health</span><HeartPulse size={16} /></div>{loading && <LoadingMessage label="Checking backend health..." />}{error && <ErrorMessage message={error} />}{health && <div className="health-list"><HealthRow icon={<Database size={14} />} label="Database" value={health.database || health.status} /><HealthRow icon={<Database size={14} />} label="pgvector" value={health.pgvector || 'Not reported'} /><HealthRow icon={<ShieldCheck size={14} />} label="MCP boundary" value={health.mcp_boundary || 'Not reported'} /></div>}</div>
      </div>
    </section>
  );
}

function HealthRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="health-row">{icon}<span>{label}</span><strong>{value}</strong></div>;
}

export function App() {
  const [activeView, setActiveView] = useState<AppView>('inquiry');
  const [userId, setUserId] = useState(initialUserId);

  return (
    <AnvikshikiShell activeView={activeView} onViewChange={setActiveView} userId={userId}>
      {activeView === 'inquiry' && <ResearchWorkspace userId={userId} />}
      {activeView === 'library' && <LibraryView />}
      {activeView === 'memory' && <MemoryView userId={userId} />}
      {activeView === 'settings' && <SettingsView userId={userId} onUserIdChange={setUserId} />}
    </AnvikshikiShell>
  );
}

export default App;
