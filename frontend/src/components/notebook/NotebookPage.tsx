import { useEffect, useState, type FormEvent } from 'react';
import { ArrowLeft, BookOpen, Check, LoaderCircle, Plus, Save, Trash2 } from 'lucide-react';
import { ApiError } from '../../api/client';
import { createNotebook, deleteNotebook, getNotebook, listNotebooks, updateNotebook } from '../../api/services';
import type { NotebookDTO } from '../../types';
import { navigate } from '../../routing';
import './NotebookPage.css';

const MAX_TITLE = 256;
const MAX_CONTENT = 100_000;

function safeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403 || error.status === 404)) {
    return 'This notebook is unavailable to the current session.';
  }
  return fallback;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString();
}

function LoadingState() {
  return <p className="muted-copy notebook-status" role="status" aria-live="polite"><LoaderCircle className="spin" size={15} /> Loading notebook…</p>;
}

function NotebookEditor({ notebookId }: { notebookId: string }) {
  const [notebook, setNotebook] = useState<NotebookDTO | null>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setSaveMessage('');
    void getNotebook(notebookId).then((value) => {
      if (!active) return;
      setNotebook(value); setTitle(value.title); setContent(value.content);
    }).catch((reason: unknown) => { if (active) setError(safeError(reason, 'Notebook could not be loaded.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [notebookId]);

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle || cleanTitle.length > MAX_TITLE || content.length > MAX_CONTENT) {
      setError('Enter a title and keep the notebook within the supported length limits.');
      return;
    }
    setSaving(true); setError(''); setSaveMessage('');
    try {
      const value = await updateNotebook(notebookId, { title: cleanTitle, content });
      setNotebook(value); setTitle(value.title); setContent(value.content); setSaveMessage('Notebook saved.');
    } catch (reason) { setError(safeError(reason, 'Notebook could not be saved.')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!window.confirm('Delete this notebook?')) return;
    setDeleting(true); setError('');
    try { await deleteNotebook(notebookId); navigate('/notebook'); }
    catch (reason) { setError(safeError(reason, 'Notebook could not be deleted.')); setDeleting(false); }
  };

  if (loading) return <LoadingState />;
  if (error && !notebook) return <section className="notebook-page"><div className="notebook-toolbar"><button className="button button-quiet" type="button" onClick={() => navigate('/notebook')}><ArrowLeft size={15} /> Back</button></div><div className="notebook-error" role="alert">{error}</div></section>;
  if (!notebook) return null;
  return <section className="notebook-page" aria-labelledby="notebook-editor-heading">
    <div className="notebook-toolbar"><button className="button button-quiet" type="button" onClick={() => navigate('/notebook')}><ArrowLeft size={15} /> Back to notebooks</button><span className="eyebrow">Owned notebook</span><button className="button button-danger" type="button" onClick={() => void remove()} disabled={deleting || saving}><Trash2 size={14} /> {deleting ? 'Deleting…' : 'Delete'}</button></div>
    <div className="eyebrow">Research notebook</div><h1 id="notebook-editor-heading">Edit notebook</h1><p className="page-lede">Plain text and Markdown are stored exactly as entered. Sources and provenance remain backend records.</p>
    <form className="notebook-editor panel" onSubmit={save}>
      <label htmlFor="notebook-title">Title</label><input id="notebook-title" value={title} maxLength={MAX_TITLE} onChange={(event) => setTitle(event.target.value)} disabled={saving || deleting} />
      <label htmlFor="notebook-content">Notes</label><textarea id="notebook-content" value={content} maxLength={MAX_CONTENT} onChange={(event) => setContent(event.target.value)} disabled={saving || deleting} rows={18} />
      <div className="notebook-editor-footer"><span className="muted-copy">Updated {formatDate(notebook.updated_at)} · {content.length.toLocaleString()} / {MAX_CONTENT} characters</span><button className="button button-primary" type="submit" disabled={saving || deleting || !title.trim()}>{saving ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />} {saving ? 'Saving…' : 'Save notebook'}</button></div>
      {saveMessage && <p className="notebook-success" role="status"><Check size={14} /> {saveMessage}</p>}
      {error && <div className="notebook-error" role="alert">{error}</div>}
    </form>
  </section>;
}

function NotebookIndex() {
  const [notebooks, setNotebooks] = useState<NotebookDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => { setLoading(true); setError(''); void listNotebooks().then(setNotebooks).catch((reason: unknown) => setError(safeError(reason, 'Notebooks could not be loaded.'))).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle || cleanTitle.length > MAX_TITLE || content.length > MAX_CONTENT) { setError('Enter a title and keep the notebook within the supported length limits.'); return; }
    setSaving(true); setError('');
    try { const value = await createNotebook({ title: cleanTitle, content }); navigate(`/notebook/${encodeURIComponent(value.notebook_id)}`); }
    catch (reason) { setError(safeError(reason, 'Notebook could not be created.')); }
    finally { setSaving(false); }
  };

  return <section className="notebook-page" aria-labelledby="notebook-heading">
    <div className="eyebrow">Workspace / Notes</div><h1 id="notebook-heading">Research notebooks</h1><p className="page-lede">Keep durable working notes beside your investigations. Notebook content is private to the authenticated session.</p>
    <div className="notebook-actions"><button className="button button-primary" type="button" onClick={() => setCreating((value) => !value)} aria-expanded={creating}><Plus size={15} /> New notebook</button></div>
    {creating && <form className="notebook-create panel" onSubmit={create}><div className="panel-heading"><span className="eyebrow">New notebook</span><BookOpen size={16} /></div><label htmlFor="new-notebook-title">Title</label><input id="new-notebook-title" value={title} maxLength={MAX_TITLE} onChange={(event) => setTitle(event.target.value)} placeholder="A question, theme, or line of inquiry" disabled={saving} /><label htmlFor="new-notebook-content">Notes</label><textarea id="new-notebook-content" value={content} maxLength={MAX_CONTENT} onChange={(event) => setContent(event.target.value)} placeholder="Write a durable research note…" rows={9} disabled={saving} /><button className="button button-primary" type="submit" disabled={saving || !title.trim()}>{saving ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />} {saving ? 'Creating…' : 'Create notebook'}</button></form>}
    {loading && <LoadingState />}{error && <div className="notebook-error" role="alert">{error}</div>}
    {!loading && !error && notebooks.length === 0 && <div className="notebook-empty panel"><BookOpen size={20} /><h2>No notebooks yet</h2><p className="muted-copy">Create a private place for durable research notes.</p></div>}
    {!loading && notebooks.length > 0 && <div className="notebook-list" aria-label="Your notebooks">{notebooks.map((item) => <button className="notebook-list-item panel" key={item.notebook_id} type="button" onClick={() => navigate(`/notebook/${encodeURIComponent(item.notebook_id)}`)}><span className="notebook-list-title">{item.title}</span><span className="notebook-list-preview">{item.content || 'Empty notebook'}</span><span className="notebook-list-date">Updated {formatDate(item.updated_at)}</span></button>)}</div>}
  </section>;
}

export function NotebookPage({ notebookId }: { notebookId?: string }) { return notebookId ? <NotebookEditor notebookId={notebookId} /> : <NotebookIndex />; }
