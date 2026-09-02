import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { AlertTriangle, Check, ChevronDown, Clock3, History, LoaderCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import { createEpistemicPosition, getEpistemicPositions, updateEpistemicPositionStatus } from '../../api/services';
import type { EpistemicPositionDTO } from '../../types';
import './MemoryPage.css';

const STATUS_OPTIONS = ['tentative', 'accepted', 'rejected', 'contested', 'under investigation', 'unresolved'];

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function payloadText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value !== 'object' || value === null) return String(value ?? 'No detail reported.');
  const record = value as Record<string, unknown>;
  const preferred = [record.text, record.statement, record.detail, record.description].find((item) => typeof item === 'string');
  return preferred ? String(preferred) : 'Structured context returned by the backend.';
}

function sortPositions(positions: EpistemicPositionDTO[]): EpistemicPositionDTO[] {
  return [...positions].sort((left, right) => {
    const timestampOrder = right.updated_at.localeCompare(left.updated_at);
    return timestampOrder || left.position_id.localeCompare(right.position_id);
  });
}

function LoadingMessage({ label }: { label: string }) {
  return <p className="muted-copy loading-message" role="status"><LoaderCircle className="spin" size={14} /> {label}</p>;
}

function ErrorMessage({ message }: { message: string }) {
  return <div className="inline-error" role="alert"><AlertTriangle size={15} />{message}</div>;
}

function PositionEvidence({ position }: { position: EpistemicPositionDTO }) {
  const evidence = position.supporting_evidence ?? [];
  const counterarguments = position.counterarguments ?? [];
  return <div className="understanding-details">
    <div>
      <span className="eyebrow">Supporting context</span>
      {evidence.length === 0 ? <p className="muted-copy">No supporting evidence was returned.</p> : <ul className="context-list">{evidence.map((item, index) => <li key={`${position.position_id}-evidence-${index}`}>{payloadText(item)}</li>)}</ul>}
    </div>
    <div>
      <span className="eyebrow">Counterarguments</span>
      {counterarguments.length === 0 ? <p className="muted-copy">No counterarguments were returned.</p> : <ul className="context-list">{counterarguments.map((item, index) => <li key={`${position.position_id}-counter-${index}`}>{payloadText(item)}</li>)}</ul>}
    </div>
  </div>;
}

function PositionHistory({ position }: { position: EpistemicPositionDTO }) {
  const history = position.history ?? [];
  return <details className="position-history">
    <summary><span><History size={14} /> Status history</span><ChevronDown size={14} /></summary>
    {history.length === 0 ? <p className="muted-copy">No status transitions have been recorded.</p> : <ol>{history.map((item, index) => <li key={`${position.position_id}-history-${index}`}><strong>{payloadText(item.previous_status)} → {payloadText(item.new_status)}</strong><span>{payloadText(item.change_reason)}</span>{typeof item.timestamp === 'string' && <small>{readableDate(item.timestamp)}</small>}</li>)}</ol>}
  </details>;
}

function PositionCard({ position, onUpdated }: { position: EpistemicPositionDTO; onUpdated: (position: EpistemicPositionDTO) => void }) {
  const [status, setStatus] = useState(position.status);
  const [reason, setReason] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const saveStatus = async () => {
    if (status === position.status) { setEditing(false); return; }
    setSaving(true);
    setError('');
    try {
      const updated = await updateEpistemicPositionStatus(position.position_id, { new_status: status, ...(reason.trim() ? { change_reason: reason.trim() } : {}) });
      onUpdated(updated);
      setReason('');
      setEditing(false);
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Understanding status could not be updated.');
    } finally {
      setSaving(false);
    }
  };

  return <article className="understanding-card">
    <div className="understanding-card-header"><span className={`status-chip ${position.status.replace(/ /g, '-')}`}>{position.status}</span><span className="understanding-date"><Clock3 size={13} /> Updated {readableDate(position.updated_at)}</span></div>
    <h2>{position.claim_statement}</h2>
    <p className="position-statement">{position.position}</p>
    <div className="confidence-row"><span className="eyebrow">Confidence</span><strong>{Math.round(position.confidence * 100)}%</strong><div className="confidence-track" role="progressbar" aria-label={`Confidence ${Math.round(position.confidence * 100)} percent`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(position.confidence * 100)}><span style={{ width: `${Math.max(0, Math.min(100, position.confidence * 100))}%` }} /></div></div>
    <PositionEvidence position={position} />
    <PositionHistory position={position} />
    <div className="position-edit">
      {!editing ? <button className="text-button" type="button" onClick={() => setEditing(true)}>Update status</button> : <div className="status-editor"><label><span className="eyebrow">New status</span><select value={status} onChange={(event) => setStatus(event.target.value)} disabled={saving}>{STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label><label><span className="eyebrow">Reason <span className="optional">optional</span></span><input value={reason} onChange={(event) => setReason(event.target.value)} disabled={saving} maxLength={500} placeholder="Why did this understanding change?" /></label><div className="editor-actions"><button className="button button-primary" type="button" onClick={() => void saveStatus()} disabled={saving || status === position.status}>{saving ? <LoaderCircle className="spin" size={14} /> : <Check size={14} />} Save status</button><button className="text-button" type="button" onClick={() => { setStatus(position.status); setReason(''); setError(''); setEditing(false); }} disabled={saving}>Cancel</button></div></div>}
      {error && <ErrorMessage message={error} />}
    </div>
  </article>;
}

interface Props { userId: string; }

export function MemoryPage({ userId }: Props) {
  const [positions, setPositions] = useState<EpistemicPositionDTO[]>([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showComposer, setShowComposer] = useState(false);
  const [claim, setClaim] = useState('');
  const [position, setPosition] = useState('');
  const [confidence, setConfidence] = useState('0.7');
  const [status, setStatus] = useState('tentative');
  const [saving, setSaving] = useState(false);

  const load = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError('');
    try {
      setPositions(sortPositions(await getEpistemicPositions(userId)));
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Understanding context could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { void load(); }, [userId]);

  const visiblePositions = useMemo(() => filter === 'all' ? positions : positions.filter((item) => item.status === filter), [filter, positions]);
  const statusCounts = useMemo(() => STATUS_OPTIONS.reduce<Record<string, number>>((counts, option) => ({ ...counts, [option]: positions.filter((item) => item.status === option).length }), {}), [positions]);

  const createPosition = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedClaim = claim.trim();
    const normalizedPosition = position.trim();
    const numericConfidence = Number(confidence);
    if (normalizedClaim.length < 5 || !normalizedPosition || !Number.isFinite(numericConfidence) || numericConfidence < 0 || numericConfidence > 1) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const created = await createEpistemicPosition({ user_id: userId, claim_statement: normalizedClaim, position: normalizedPosition, confidence: numericConfidence, status });
      setPositions((current) => sortPositions([created, ...current]));
      setClaim('');
      setPosition('');
      setConfidence('0.7');
      setStatus('tentative');
      setShowComposer(false);
      setNotice('Understanding position recorded.');
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Understanding position could not be recorded.');
    } finally {
      setSaving(false);
    }
  };

  return <section className="secondary-page memory-page" aria-busy={loading || refreshing}>
    <div className="eyebrow">Knowledge / Memory / Understanding</div>
    <div className="memory-title-row"><div><h1>Current understanding</h1><p className="page-lede">Your epistemic positions provide continuity for research. They remain user context, not automatically verified source evidence.</p></div><div className="memory-actions"><button className="button" type="button" onClick={() => void load(true)} disabled={loading || refreshing}><RefreshCw className={refreshing ? 'spin' : undefined} size={14} /> Refresh</button><button className="button button-primary" type="button" onClick={() => { setShowComposer((value) => !value); setError(''); }} aria-expanded={showComposer}><Plus size={14} /> Record position</button></div></div>
    <div className="memory-boundary" role="note"><ShieldCheck size={16} /><span><strong>Private epistemic context.</strong> The authenticated backend scopes this view to your session. Other memory tiers remain unavailable here because no corresponding frontend API contract exists.</span></div>
    {notice && <div className="success-callout" role="status">{notice}</div>}
    {showComposer && <form className="memory-composer panel" onSubmit={createPosition}><div className="panel-heading"><span className="eyebrow">New epistemic position</span><span className="muted-copy">Saved to your authenticated context</span></div><div className="composer-fields"><label><span className="eyebrow">Claim or question</span><textarea value={claim} onChange={(event) => setClaim(event.target.value)} minLength={5} maxLength={2000} required rows={3} placeholder="What proposition should remain visible in future inquiry?" /></label><label><span className="eyebrow">Your position</span><textarea value={position} onChange={(event) => setPosition(event.target.value)} maxLength={2000} required rows={3} placeholder="How do you currently understand it?" /></label><label><span className="eyebrow">Confidence (0–1)</span><input type="number" value={confidence} onChange={(event) => setConfidence(event.target.value)} min="0" max="1" step="0.01" required /></label><label><span className="eyebrow">Initial status</span><select value={status} onChange={(event) => setStatus(event.target.value)}>{STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label></div><div className="composer-actions"><button className="button button-primary" type="submit" disabled={saving || claim.trim().length < 5 || !position.trim()}>{saving ? <LoaderCircle className="spin" size={14} /> : <Check size={14} />} Save position</button><button className="text-button" type="button" onClick={() => setShowComposer(false)} disabled={saving}>Cancel</button></div></form>}
    <section className="memory-overview" aria-label="Understanding summary"><div><span className="eyebrow">Positions</span><strong>{positions.length}</strong><small>owned records returned</small></div><div><span className="eyebrow">Active filter</span><strong>{filter === 'all' ? 'All' : filter}</strong><small>{visiblePositions.length} visible</small></div><div><span className="eyebrow">Continuity boundary</span><strong>Context</strong><small>not source evidence</small></div></section>
    <div className="memory-filter" aria-label="Filter understanding positions"><span className="eyebrow">Show</span><button type="button" className={filter === 'all' ? 'selected' : ''} onClick={() => setFilter('all')}>All <span>{positions.length}</span></button>{STATUS_OPTIONS.map((option) => <button type="button" className={filter === option ? 'selected' : ''} onClick={() => setFilter(option)} key={option}>{option} <span>{statusCounts[option]}</span></button>)}</div>
    {loading && <LoadingMessage label="Loading your understanding..." />}
    {!loading && error && <ErrorMessage message={error} />}
    {!loading && !error && visiblePositions.length === 0 && <div className="empty-card"><ShieldCheck size={18} />{positions.length === 0 ? 'No epistemic positions are currently recorded for this user.' : 'No positions match the selected status.'}</div>}
    {!loading && !error && visiblePositions.length > 0 && <div className="understanding-list">{visiblePositions.map((item) => <PositionCard key={item.position_id} position={item} onUpdated={(updated) => { setPositions((current) => sortPositions(current.map((candidate) => candidate.position_id === updated.position_id ? updated : candidate))); setNotice('Understanding status updated.'); }} />)}</div>}
  </section>;
}
