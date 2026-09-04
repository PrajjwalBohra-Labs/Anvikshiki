import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, CircleDot, Database, FileSearch, LoaderCircle, Network, Share2 } from 'lucide-react';
import { ApiError } from '../../api/client';
import { getRunProvenanceGraph, listResearchRuns } from '../../api/services';
import { navigate } from '../../routing';
import type { ProvenanceEdgeDTO, ProvenanceGraphDTO, ProvenanceNodeDTO, ResearchRunSummaryDTO } from '../../types';
import './KnowledgeGraphPage.css';

const NODE_GROUP_ORDER = ['RESEARCH_RUN', 'SOURCE', 'DOCUMENT', 'DOCUMENT_VERSION', 'PAGE', 'PASSAGE', 'CLAIM', 'EVIDENCE', 'VALIDATION', 'SYNTHESIS', 'SPECIALIST_ANALYSIS'];

function Loading({ label }: { label: string }) {
  return <p className="muted-copy loading-message" role="status"><LoaderCircle className="spin" size={14} /> {label}</p>;
}

function Failure({ message }: { message: string }) {
  return <div className="inline-error" role="alert"><AlertTriangle size={15} />{message}</div>;
}

function safeErrorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) return 'Sign in to inspect research provenance.';
    if (reason.status === 403 || reason.status === 404) return 'This research run is unavailable to the current session.';
    if (reason.status >= 500 || reason.status === 0) return 'The knowledge graph service is temporarily unavailable.';
  }
  return 'Knowledge graph could not be loaded.';
}

function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not reported';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not reported' : date.toLocaleString();
}

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === undefined) return 'Not reported';
  try {
    return JSON.stringify(value) ?? 'Not reported';
  } catch {
    return 'Structured metadata';
  }
}

function nodeGroupLabel(nodeType: string): string {
  return nodeType.replace(/_/g, ' ');
}

function GraphNode({ node, selected, onSelect }: { node: ProvenanceNodeDTO; selected: boolean; onSelect: () => void }) {
  return <button type="button" className={`graph-node ${selected ? 'selected' : ''}`} aria-pressed={selected} onClick={onSelect}>
    <span className="graph-node-type">{nodeGroupLabel(node.node_type)}</span>
    <strong>{node.label}</strong>
    <small>{node.entity_id}</small>
  </button>;
}

function NodeDetail({ node }: { node: ProvenanceNodeDTO }) {
  const metadata = Object.entries(node.metadata ?? {});
  return <aside className="graph-selection panel" aria-label="Selected graph node">
    <div className="panel-heading"><span className="eyebrow">Selected node</span><Network size={15} /></div>
    <div className="graph-selection-body"><span className="graph-node-type">{nodeGroupLabel(node.node_type)}</span><h2>{node.label}</h2><p className="muted-copy">Entity {node.entity_id}</p><p className="muted-copy">Created {formatDate(node.created_at)}</p>{metadata.length > 0 && <dl className="metadata-list">{metadata.map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd>{displayValue(value)}</dd></div>)}</dl>}{metadata.length === 0 && <p className="muted-copy">No additional metadata was returned.</p>}</div>
  </aside>;
}

function GraphEdges({ edges, nodesById }: { edges: ProvenanceEdgeDTO[]; nodesById: Map<string, ProvenanceNodeDTO> }) {
  return <section className="graph-edges panel" aria-label="Graph relationships"><div className="panel-heading"><span className="eyebrow">Relationships</span><span className="muted-copy">{edges.length} returned</span></div>{edges.length === 0 ? <p className="muted-copy section-pad">No graph relationships were returned.</p> : <ol>{edges.map((edge) => <li key={edge.edge_id}><span className="edge-endpoint">{nodesById.get(edge.from_node_id)?.label ?? edge.from_node_id}</span><ArrowRight size={14} aria-hidden="true" /><span className="edge-relation">{nodeGroupLabel(edge.relationship_type)}</span><ArrowRight size={14} aria-hidden="true" /><span className="edge-endpoint">{nodesById.get(edge.to_node_id)?.label ?? edge.to_node_id}</span><small>{edge.edge_id} / {formatDate(edge.created_at)}</small></li>)}</ol>}</section>;
}

function GraphCanvas({ graph }: { graph: ProvenanceGraphDTO }) {
  const [selectedId, setSelectedId] = useState<string | null>(graph.nodes[0]?.node_id ?? null);
  const nodesById = useMemo(() => new Map(graph.nodes.map((node) => [node.node_id, node])), [graph.nodes]);
  const groups = useMemo(() => {
    const order = new Map(NODE_GROUP_ORDER.map((type, index) => [type, index]));
    const grouped = new Map<string, ProvenanceNodeDTO[]>();
    [...graph.nodes].sort((left, right) => left.node_id.localeCompare(right.node_id)).forEach((node) => {
      const list = grouped.get(node.node_type) ?? [];
      list.push(node);
      grouped.set(node.node_type, list);
    });
    return [...grouped.entries()].sort(([left], [right]) => (order.get(left) ?? NODE_GROUP_ORDER.length) - (order.get(right) ?? NODE_GROUP_ORDER.length));
  }, [graph.nodes]);
  const selectedNode = selectedId ? nodesById.get(selectedId) : undefined;
  return <>
    <div className="graph-layout">
      <section className="graph-canvas panel" aria-label="Knowledge graph nodes"><div className="panel-heading"><span className="eyebrow">Graph map</span><span className="muted-copy">{graph.nodes.length} nodes / {graph.edges.length} edges</span></div>{graph.nodes.length === 0 ? <p className="muted-copy section-pad">The backend returned an empty graph.</p> : <div className="graph-groups">{groups.map(([type, nodes]) => <section className="graph-group" key={type}><div className="graph-group-heading"><span>{nodeGroupLabel(type)}</span><small>{nodes.length}</small></div><div className="graph-node-list">{nodes.map((node) => <GraphNode key={node.node_id} node={node} selected={node.node_id === selectedId} onSelect={() => setSelectedId(node.node_id)} />)}</div></section>)}</div>}</section>
      {selectedNode && <NodeDetail node={selectedNode} />}
    </div>
    <GraphEdges edges={graph.edges} nodesById={nodesById} />
  </>;
}

function RunChooser({ runs }: { runs: ResearchRunSummaryDTO[] }) {
  return <div className="graph-run-list">{runs.map((run) => <button className="record-card" type="button" key={run.run_id} onClick={() => navigate(`/knowledge-graph/${encodeURIComponent(run.run_id)}`)}><span className="record-icon"><FileSearch size={17} /></span><span className="record-main"><strong>{run.query}</strong><small>{run.domain || 'Domain not reported'} / Started {formatDate(run.started_at)}</small></span><span className="status-chip">{run.status}</span><ArrowRight size={15} /></button>)}</div>;
}

export function KnowledgeGraphPage({ runId }: { runId?: string }) {
  const [runs, setRuns] = useState<ResearchRunSummaryDTO[]>([]);
  const [graph, setGraph] = useState<ProvenanceGraphDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setGraph(null);
    const load = runId ? getRunProvenanceGraph(runId) : listResearchRuns();
    void load.then((value) => {
      if (!active) return;
      if (runId) setGraph(value as ProvenanceGraphDTO); else setRuns(value as ResearchRunSummaryDTO[]);
    }).catch((reason: unknown) => { if (active) setError(safeErrorMessage(reason)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [runId]);

  if (loading) return <section className="secondary-page"><Loading label={runId ? 'Loading provenance graph...' : 'Loading research runs...'} /></section>;
  if (error) return <section className="secondary-page"><Failure message={error} /><button className="button" type="button" onClick={() => navigate('/knowledge-graph')}>Back to graph index</button></section>;
  if (!runId) return <section className="secondary-page knowledge-page"><div className="eyebrow">Knowledge / Provenance graph</div><h1>Knowledge graph</h1><p className="page-lede">Choose an authenticated research run to inspect the graph assembled from its returned provenance records.</p><div className="graph-boundary" role="note"><Database size={15} /><span>Only backend-returned nodes and edges are shown. No relationships are inferred in the browser.</span></div>{runs.length === 0 ? <div className="empty-card"><CircleDot size={18} />No research runs are currently available for this session.</div> : <RunChooser runs={runs} />}</section>;
  return <section className="secondary-page knowledge-page"><div className="eyebrow">Knowledge / Provenance graph</div><button className="text-button graph-back" type="button" onClick={() => navigate('/knowledge-graph')}><ArrowLeft size={13} /> Back to graph index</button><h1>Provenance graph</h1><p className="page-lede">A structured view of the nodes and relationships returned for research run <code>{runId}</code>.</p><div className="graph-boundary" role="note"><Share2 size={15} /><span>Edges are rendered exactly from the backend graph contract. Select a node to inspect its public metadata.</span></div><GraphCanvas graph={graph ?? { nodes: [], edges: [] }} /></section>;
}
