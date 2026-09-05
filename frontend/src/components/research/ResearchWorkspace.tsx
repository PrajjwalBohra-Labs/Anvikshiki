import { useState, type FormEvent } from 'react';
import { AlertTriangle, BookOpen, Check, CheckCircle2, CircleDot, Database, GitBranch, Layers3, LoaderCircle, MessageCircle, Search, ShieldCheck, Square, Terminal } from 'lucide-react';
import { useResearchStream, type ResearchStreamState } from '../../hooks/useResearchStream';
import { executeDialogue, searchPassages } from '../../api/services';
import { navigate } from '../../routing';
import type { DialogueTurnDTO, SearchResultDTO } from '../../types';
import './ResearchWorkspace.css';

interface Props { userId: string; }

const stageLabels: Record<string, string> = {
  coordinator: 'Question understood',
  web_research: 'Discovering and acquiring web sources',
  retrieval: 'Retrieving indexed evidence',
  specialist_analysis: 'Running specialist analysis',
  challenger: 'Examining challenges',
  validator: 'Validating synthesis',
};

const workflowStages = [
  { label: 'Question', node: 'coordinator' },
  { label: 'Web sources', node: 'web_research' },
  { label: 'Retrieval', node: 'retrieval' },
  { label: 'Specialist analysis', node: 'specialist_analysis' },
  { label: 'Challenge', node: 'challenger' },
  { label: 'Validation', node: 'validator' },
  { label: 'Synthesis', node: 'synthesis' },
];

function ResearchWorkflow({ state }: { state: ResearchStreamState }) {
  const lastNode = [...state.activity].reverse().find((item) => item.node)?.node;
  return <section className="workflow-panel" aria-label="Research workflow">
    <div className="workflow-heading"><span className="eyebrow">Investigation path</span><span className="muted-copy">Question → synthesis</span></div>
    <ol className="workflow-strip">
      {workflowStages.map((stage) => {
        const present = state.activity.some((item) => item.node === stage.node);
        const active = state.status === 'streaming' && lastNode === stage.node;
        const complete = present && !active;
        return <li className={`${present ? 'present ' : ''}${active ? 'active ' : ''}${complete ? 'complete' : ''}`} key={stage.label}><span className="workflow-marker">{complete ? <Check size={12} /> : <span />}</span><strong>{stage.label}</strong></li>;
      })}
    </ol>
  </section>;
}

function IntelligenceSidebar({ state, evidenceResults }: { state: ResearchStreamState; evidenceResults: SearchResultDTO[] }) {
  const result = state.result;
  const passages = result?.retrieved_passages ?? [];
  const sourceCount = new Set(passages.map((passage) => passage.source_id || passage.source_title)).size;
  const claimCount = result?.claims.length ?? 0;
  const analysisCount = result ? Object.values(result.specialist_analysis).reduce((total, group) => total + group.length, 0) : 0;
  const categories = [
    { label: 'EVIDENCE', value: passages.length || evidenceResults.length, note: passages.length ? 'retrieved passages' : evidenceResults.length ? 'lookup passages' : 'not reported', icon: BookOpen, tone: 'evidence' },
    { label: 'SOURCES', value: sourceCount || '—', note: sourceCount ? 'represented in result' : 'not reported', icon: Database, tone: 'archival' },
    { label: 'CLAIMS', value: claimCount || '—', note: claimCount ? 'returned claims' : 'not reported', icon: CheckCircle2, tone: 'interpretation' },
    { label: 'ARGUMENTS', value: analysisCount || '—', note: analysisCount ? 'specialist fields' : 'not reported', icon: GitBranch, tone: 'scientific' },
    { label: 'CONCEPTS', value: '—', note: 'not exposed by current run', icon: Layers3, tone: 'hypothesis' },
    { label: 'MEMORY', value: '—', note: 'not exposed by current run', icon: ShieldCheck, tone: 'memory' },
    { label: 'ACTIVITY', value: state.activity.length, note: state.status === 'idle' ? 'awaiting research' : state.status, icon: Terminal, tone: state.status === 'failed' ? 'contradiction' : 'activity' },
  ];
  return <aside className="intelligence-sidebar" aria-label="Research intelligence">
    <div className="intelligence-top"><div><span className="eyebrow">Intelligence</span><h2>Research signals</h2></div><span className="intelligence-pip" aria-hidden="true" /></div>
    <p className="intelligence-intro">A compact view of relationships returned by the current investigation.</p>
    <div className="intelligence-list">
      {categories.map(({ label, value, note, icon: Icon, tone }) => <div className={`intelligence-item ${tone}`} key={label}><Icon size={14} /><div><strong>{label}</strong><small>{note}</small></div><b>{value}</b></div>)}
    </div>
    <div className="intelligence-trace"><span className="eyebrow">Trace boundary</span><p><span>Source</span><i>→</i><span>Passage</span><i>→</i><span>Claim</span></p><small>Only relationships returned by the backend are shown.</small></div>
  </aside>;
}

export function ResearchWorkspace({ userId }: Props) {
  const [query, setQuery] = useState('');
  const [domain, setDomain] = useState('Philosophy & Empirical Epistemology');
  const [includeWeb, setIncludeWeb] = useState(false);
  const [evidenceQuery, setEvidenceQuery] = useState('');
  const [evidenceResults, setEvidenceResults] = useState<SearchResultDTO[]>([]);
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [dialogueInput, setDialogueInput] = useState('');
  const [dialogueMode, setDialogueMode] = useState('socratic');
  const [dialogueTurn, setDialogueTurn] = useState<DialogueTurnDTO | null>(null);
  const [dialogueError, setDialogueError] = useState('');
  const [dialogueLoading, setDialogueLoading] = useState(false);
  const { state, run, cancel } = useResearchStream(userId);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized.length < 3 || !userId) return;
    await run(normalized, domain, includeWeb);
  };

  const isRunning = state.status === 'streaming';
  const isCancelled = state.status === 'cancelled';
  const canSubmit = query.trim().length >= 3 && Boolean(userId) && !isRunning;

  const searchEvidence = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = evidenceQuery.trim();
    if (normalized.length < 2) return;
    setEvidenceLoading(true);
    setEvidenceError('');
    try {
      const response = await searchPassages(normalized);
      setEvidenceResults(response.results);
    } catch (error) {
      setEvidenceResults([]);
      setEvidenceError(error instanceof Error ? error.message : 'Evidence search failed.');
    } finally {
      setEvidenceLoading(false);
    }
  };

  const submitDialogue = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = dialogueInput.trim();
    if (!normalized) return;
    setDialogueLoading(true);
    setDialogueError('');
    try {
      setDialogueTurn(await executeDialogue(normalized, dialogueMode));
      setDialogueInput('');
    } catch (error) {
      setDialogueError(error instanceof Error ? error.message : 'Dialogue response failed.');
    } finally {
      setDialogueLoading(false);
    }
  };

  return (
    <div className="research-page">
      <section className="research-intro">
        <div className="eyebrow">Inquiry / Research mode</div>
        <h1>What are you investigating?</h1>
        <p>Ask a question that deserves sources, arguments, and uncertainty made visible.</p>
      </section>

      <div className="research-cockpit">
        <div className="research-core">

      <form className="inquiry-form" onSubmit={submit}>
        <label htmlFor="research-question" className="eyebrow">Research question</label>
        <textarea
          id="research-question"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask a question, investigate a claim, or examine an unresolved problem..."
          rows={4}
          maxLength={10000}
          disabled={isRunning}
        />
        <div className="inquiry-controls">
          <label className="domain-control" htmlFor="research-domain">
            <span className="eyebrow">Domain</span>
            <select id="research-domain" value={domain} onChange={(event) => setDomain(event.target.value)} disabled={isRunning}>
              <option>Philosophy &amp; Empirical Epistemology</option>
              <option>Epistemology</option>
              <option>Neuroscience and Cognition</option>
            </select>
          </label>
          <label className="web-control" htmlFor="research-web">
            <span className="eyebrow">External sources</span>
            <span><input id="research-web" type="checkbox" checked={includeWeb} onChange={(event) => setIncludeWeb(event.target.checked)} disabled={isRunning} /> Include web discovery and acquisition</span>
          </label>
          <div className="inquiry-actions">
            {!userId && <span className="configuration-note">Configure a valid backend user ID in Settings.</span>}
            {isRunning ? (
              <button className="button button-critical" type="button" onClick={cancel}><Square size={14} /> Stop run</button>
            ) : (
              <button className="button button-primary" type="submit" disabled={!canSubmit}><Search size={15} /> Begin investigation</button>
            )}
          </div>
        </div>
      </form>

      <ResearchWorkflow state={state} />

      {state.status === 'idle' && (
        <section className="workspace-empty" aria-label="Research guidance">
          <div className="empty-symbol"><CircleDot size={23} /></div>
          <div><h2>Nothing is being investigated</h2><p>The workspace will show only activity and results returned by the research engine.</p></div>
        </section>
      )}

      {state.status !== 'idle' && (
        <section className="run-layout" aria-live="polite">
          <div className="activity-panel panel">
            <div className="panel-heading"><span className="eyebrow">Research activity</span>{isRunning && <LoaderCircle className="spin" size={16} aria-label="Research active" />}</div>
            <ol className="activity-list">
              {state.activity.map((item) => (
                <li key={item.key} className={item.event === 'research_completed' ? 'complete' : ''}>
                  <span className="activity-icon">{item.event === 'research_completed' ? <Check size={14} /> : <Terminal size={13} />}</span>
                  <span><strong>{stageLabels[item.node ?? ''] ?? item.event.replace(/_/g, ' ')}</strong><small>{item.summary}</small></span>
                  <em>{item.status}</em>
                </li>
              ))}
              {isRunning && <li className="activity-pending"><span className="activity-icon"><LoaderCircle className="spin" size={14} /></span><span><strong>Waiting for next backend event</strong><small>No progress is simulated.</small></span></li>}
            </ol>
          </div>

          <div className="result-panel panel">
            <div className="panel-heading"><span className="eyebrow">Research output</span>{state.validationStatus && <span className="status-label">{state.validationStatus}</span>}{isCancelled && <span className="status-label">CANCELLED</span>}</div>
            {state.finalResponse ? (
              <article className="synthesis"><div className="eyebrow">Validated workflow output</div><p>{state.finalResponse}</p>{state.validatedClaimsCount !== undefined && <div className="result-meta">{state.validatedClaimsCount} validated claim{state.validatedClaimsCount === 1 ? '' : 's'}</div>}{typeof state.result?.web_research?.status === 'string' && state.result.web_research.status !== 'skipped' && <div className="result-meta">Web research: {state.result.web_research.status}</div>}</article>
            ) : (
              <div className="result-waiting"><LoaderCircle className="spin" size={18} /><p>The final synthesis will appear when the backend emits <code>research_completed</code>.</p></div>
            )}
            {state.result && state.runId && <button className="button button-primary result-detail-link" type="button" onClick={() => navigate(`/research/runs/${encodeURIComponent(state.runId || '')}`)}>Open complete research record</button>}
            {isCancelled && <div className="cancelled-callout" role="status"><Square size={15} /><span>Research was cancelled before the backend emitted a final result. Start a new investigation when ready.</span></div>}
            {state.error && <div className="error-callout" role="alert"><AlertTriangle size={16} /><span>{state.error}</span></div>}
          </div>
        </section>
      )}

      <section className="evidence-explorer panel">
        <div className="panel-heading"><span className="eyebrow">Evidence lookup</span><span className="muted-copy">Hybrid search returned by backend</span></div>
        <form className="evidence-search" onSubmit={searchEvidence}>
          <label htmlFor="evidence-query" className="sr-only">Search indexed evidence</label>
          <input id="evidence-query" value={evidenceQuery} onChange={(event) => setEvidenceQuery(event.target.value)} placeholder="Search indexed passages..." />
          <button className="button button-primary" type="submit" disabled={evidenceLoading || evidenceQuery.trim().length < 2}>{evidenceLoading ? <LoaderCircle className="spin" size={14} /> : <Search size={14} />} Search evidence</button>
        </form>
        {evidenceError && <div className="error-callout" role="alert"><AlertTriangle size={16} /><span>{evidenceError}</span></div>}
        {!evidenceError && !evidenceLoading && evidenceQuery && evidenceResults.length === 0 && <p className="evidence-empty muted-copy">No passages returned for this query.</p>}
        <div className="evidence-results">
          {evidenceResults.map((result) => (
            <article className="evidence-card" key={result.passage_id}>
              <div className="evidence-card-heading"><span className="eyebrow">Passage / {result.source_title}</span><span className="evidence-score">{result.relevance_score.toFixed(3)}</span></div>
              <p>{result.content}</p>
              <footer><span>{result.page_number ? 'Page ' + result.page_number : 'Page not reported'}</span><span>{result.citation_string}</span></footer>
            </article>
          ))}
        </div>
      </section>

      <section className="dialogue-panel panel">
        <div className="panel-heading"><span className="eyebrow">Reflective dialogue</span><MessageCircle size={16} /></div>
        <p className="panel-intro">Continue examining a question through the backend dialogue engine. This is a separate turn, not a fabricated extension of the research stream.</p>
        <form className="dialogue-form" onSubmit={submitDialogue}>
          <label htmlFor="dialogue-mode" className="sr-only">Dialogue mode</label>
          <select id="dialogue-mode" value={dialogueMode} onChange={(event) => setDialogueMode(event.target.value)} disabled={dialogueLoading}>
            <option value="socratic">Socratic</option>
            <option value="challenge">Challenge</option>
            <option value="explanation">Explanation</option>
            <option value="counterexample">Counterexample</option>
            <option value="debate">Debate</option>
            <option value="reflective">Reflective</option>
          </select>
          <label htmlFor="dialogue-input" className="sr-only">Dialogue prompt</label>
          <input id="dialogue-input" value={dialogueInput} onChange={(event) => setDialogueInput(event.target.value)} placeholder="Ask for a challenge, clarification, or counterexample..." disabled={dialogueLoading} />
          <button className="button button-primary" type="submit" disabled={dialogueLoading || !dialogueInput.trim()}>{dialogueLoading ? <LoaderCircle className="spin" size={14} /> : <MessageCircle size={14} />} Send</button>
        </form>
        {dialogueError && <div className="error-callout" role="alert"><AlertTriangle size={16} /><span>{dialogueError}</span></div>}
        {dialogueTurn && <article className="dialogue-response"><div className="eyebrow">{dialogueTurn.dialogue_mode} response{dialogueTurn.source_title ? ' · ' + dialogueTurn.source_title : ''}</div><p>{dialogueTurn.response_text}</p><div className="dialogue-flags"><span>{dialogueTurn.evidence_linked ? 'Evidence linked' : 'No evidence linked'}</span><span>{dialogueTurn.preserves_uncertainty ? 'Uncertainty preserved' : 'Uncertainty not reported'}</span>{dialogueTurn.disagrees_with_user && <span>Challenges the premise</span>}</div></article>}
      </section>
        </div>
        <IntelligenceSidebar state={state} evidenceResults={evidenceResults} />
      </div>
    </div>
  );
}
