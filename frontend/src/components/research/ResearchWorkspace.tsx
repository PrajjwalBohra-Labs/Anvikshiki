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
  synthesis: 'Composing the synthesis',
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
    <div className="workflow-heading"><span className="workflow-sigil" aria-hidden="true"><img src="/anvikshiki-logo.png" alt="" /></span><span className="eyebrow">Investigation path</span><span className="muted-copy">Question to synthesis</span></div>
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
  const webResearch = result?.web_research;
  const passages = result?.retrieved_passages ?? [];
  const sourceCount = new Set(passages.map((passage) => passage.source_id || passage.source_title)).size;
  const claimCount = result?.claims.length ?? 0;
  const analysisCount = result ? Object.values(result.specialist_analysis).reduce((total, group) => total + group.length, 0) : 0;
  const categories = [
    { label: 'EVIDENCE', value: passages.length || evidenceResults.length, note: passages.length ? 'retrieved passages' : evidenceResults.length ? 'lookup passages' : 'not reported', icon: BookOpen, tone: 'evidence' },
    { label: 'SOURCES', value: sourceCount || '-', note: sourceCount ? 'represented in result' : 'not reported', icon: Database, tone: 'archival' },
    { label: 'CLAIMS', value: claimCount || '-', note: claimCount ? 'returned claims' : 'not reported', icon: CheckCircle2, tone: 'interpretation' },
    { label: 'ARGUMENTS', value: analysisCount || '-', note: analysisCount ? 'specialist fields' : 'not reported', icon: GitBranch, tone: 'scientific' },
    { label: 'CONCEPTS', value: '-', note: 'not exposed by current run', icon: Layers3, tone: 'hypothesis' },
    { label: 'MEMORY', value: '-', note: 'not exposed by current run', icon: ShieldCheck, tone: 'memory' },
    { label: 'ACTIVITY', value: state.activity.length, note: state.status === 'idle' ? 'awaiting research' : state.status, icon: Terminal, tone: state.status === 'failed' ? 'contradiction' : 'activity' },
    ...(webResearch ? [{ label: 'WEB', value: webResearch.acquired_sources.length, note: webResearch.status.replace(/_/g, ' '), icon: Search, tone: 'archival' }] : []),
  ];
  return <aside className="intelligence-sidebar" aria-label="Research intelligence">
    <div className="intelligence-top"><div><span className="eyebrow">Intelligence</span><h2>Research signals</h2></div><span className="intelligence-pip" aria-hidden="true" /></div>
    <p className="intelligence-intro">A compact view of relationships returned by the current investigation.</p>
    <div className="intelligence-list">
      {categories.map(({ label, value, note, icon: Icon, tone }) => <div className={`intelligence-item ${tone}`} key={label}><Icon size={14} /><div><strong>{label}</strong><small>{note}</small></div><b>{value}</b></div>)}
    </div>
    <div className="intelligence-trace"><span className="eyebrow">Trace boundary</span><p><span>Source</span><i>-&gt;</i><span>Passage</span><i>-&gt;</i><span>Claim</span></p><small>Only relationships returned by the backend are shown.</small></div>
  </aside>;
}

function EvidenceUsed({ result }: { result: NonNullable<ResearchStreamState['result']> }) {
  if (result.retrieved_passages.length === 0) return null;
  return <section className="synthesis-evidence" aria-label="Evidence used in this synthesis">
    <div className="eyebrow">Evidence used</div>
    <p className="muted-copy">These passages were retrieved and persisted by the backend. The model response is not a substitute for reading them.</p>
    <div className="synthesis-evidence-list">
      {result.retrieved_passages.slice(0, 5).map((passage, index) => <details key={passage.passage_id}>
        <summary><span className="evidence-identity"><span className="evidence-artifact" aria-hidden="true">P{index + 1}</span><span>{passage.source_title}</span></span><span>{passage.page_number ? `p. ${passage.page_number}` : 'page not reported'}</span></summary>
        <p>{passage.content}</p>
        {passage.citation_string && <small className="muted-copy">{passage.citation_string}</small>}
      </details>)}
    </div>
  </section>;
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
    <div className={`research-page ${query.trim() && !isRunning ? 'is-formulating' : ''} ${isRunning ? 'is-investigating' : ''} ${state.result ? 'has-synthesis' : ''}`}>
      <div className="research-atmosphere" aria-hidden="true"><span /><span /><span /></div>
      <section className="research-intro" aria-labelledby="research-heading">
        <div className="research-intro-top"><span className="eyebrow">Inquiry / Research mode</span><span className="research-coordinate">ANV / 01</span></div>
        <h1 id="research-heading">What are you<br /><em>investigating?</em></h1>
        <div className="research-intro-foot"><p>Ask a question that deserves sources, arguments, and uncertainty made visible.</p><span className="intro-rule" aria-hidden="true" /></div>
      </section>

      <div className="research-cockpit">
        <div className="research-core">

      <form className="inquiry-form" onSubmit={submit}>
        <div className="inquiry-form-heading"><span className="eyebrow">01 / Compose inquiry</span><span className="inquiry-hint">A precise question opens the archive</span></div>
        <label htmlFor="research-question" className="question-label"><span className="eyebrow">Research question</span><span className="question-count">{query.length.toLocaleString()} / 10,000</span></label>
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
          <div className="empty-symbol"><img src="/anvikshiki-logo.png" alt="" /><CircleDot size={13} /></div>
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
            <div className="panel-heading"><span className="result-heading"><span className="result-sigil" aria-hidden="true" /><span className="eyebrow">Research output</span></span>{state.validationStatus && <span className="status-label">{state.validationStatus}</span>}{isCancelled && <span className="status-label">CANCELLED</span>}</div>
            {state.finalResponse ? (
<<<<<<< HEAD
              <article className="synthesis"><div className="eyebrow">Validated workflow output</div><p>{state.finalResponse}</p>{state.validatedClaimsCount !== undefined && <div className="result-meta">{state.validatedClaimsCount} validated claim{state.validatedClaimsCount === 1 ? '' : 's'}</div>}{typeof state.result?.web_research?.status === 'string' && state.result.web_research.status !== 'skipped' && <div className="result-meta">Web research: {state.result.web_research.status}</div>}</article>
=======
              <article className="synthesis"><div className="eyebrow">Evidence-grounded workflow output</div><p>{state.finalResponse}</p>{state.result?.web_research && <div className="research-source-note">External research: {state.result.web_research.status.replace(/_/g, ' ')}; {state.result.web_research.acquired_sources.length} acquired source{state.result.web_research.acquired_sources.length === 1 ? '' : 's'}.</div>}{state.validatedClaimsCount !== undefined && <div className="result-meta">{state.validatedClaimsCount} validated claim{state.validatedClaimsCount === 1 ? '' : 's'} / {state.result?.retrieved_passages.length ?? 0} retrieved passage{state.result?.retrieved_passages.length === 1 ? '' : 's'}</div>}{state.result && <EvidenceUsed result={state.result} />}</article>
>>>>>>> origin/main
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
        <div className="panel-heading"><span className="eyebrow">03 / Evidence desk</span><span className="muted-copy">Hybrid search returned by backend</span></div>
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
              <div className="evidence-card-heading"><span className="evidence-identity"><span className="evidence-artifact" aria-hidden="true">P</span><span className="eyebrow">Passage / {result.source_title}</span></span><span className="evidence-score">{result.relevance_score.toFixed(3)}</span></div>
              <p>{result.content}</p>
              <footer><span>{result.page_number ? 'Page ' + result.page_number : 'Page not reported'}</span><span>{result.citation_string}</span></footer>
            </article>
          ))}
        </div>
      </section>

      <section className={`dialogue-panel panel dialogue-mode-${dialogueMode}`}>
        <div className="panel-heading"><span className="eyebrow">04 / Reflective dialogue</span><MessageCircle size={16} /></div>
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
        {dialogueTurn && <article className="dialogue-response"><div className="eyebrow">{dialogueTurn.dialogue_mode} response{dialogueTurn.source_title ? ' / ' + dialogueTurn.source_title : ''}</div><p>{dialogueTurn.response_text}</p><div className="dialogue-flags"><span>{dialogueTurn.evidence_linked ? 'Evidence linked' : 'No evidence linked'}</span><span>{dialogueTurn.preserves_uncertainty ? 'Uncertainty preserved' : 'Uncertainty not reported'}</span>{dialogueTurn.disagrees_with_user && <span>Challenges the premise</span>}</div></article>}
      </section>
        </div>
        <IntelligenceSidebar state={state} evidenceResults={evidenceResults} />
      </div>
    </div>
  );
}
