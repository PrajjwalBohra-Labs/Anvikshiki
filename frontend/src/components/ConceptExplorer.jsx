import { useEffect, useState } from "react"
import { Network, List, GitBranch } from "lucide-react"
import { api } from "../api"
import GraphView from "./GraphView"
import { EmptyState, Skeleton } from "./shared"

export default function ConceptExplorer() {
  const [concepts, setConcepts] = useState(null)
  const [graph, setGraph] = useState(null)
  const [view, setView] = useState("graph")

  useEffect(() => {
    api.listConcepts().then(setConcepts)
    api.getConceptGraph().then(setGraph)
  }, [])

  return (
    <div className="panel">
      <div className="panel-header-row">
        <h2><Network size={20} strokeWidth={1.75} /> Concepts</h2>
        <div className="view-switch">
          <button className={view === "graph" ? "active" : ""} onClick={() => setView("graph")}>
            <GitBranch size={12} /> Graph
          </button>
          <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>
            <List size={12} /> List
          </button>
        </div>
      </div>

      {view === "graph" ? (
        graph ? (
          <>
            <GraphView
              nodes={graph.nodes}
              edges={graph.edges}
              getNodeLabel={(n) => n.name}
            />
            <div className="graph-legend">
              <span><span className="legend-dot legend-concept" /> Concept</span>
              <span><span className="legend-dot legend-document" /> Document</span>
              <span className="hint">Edges show real relationships (e.g. derived_from) -- not inferred.</span>
            </div>
          </>
        ) : (
          <Skeleton height="380px" />
        )
      ) : (
        <ul className="list">
          {concepts === null && [1, 2].map((i) => <li key={i}><Skeleton height="1.4rem" /></li>)}
          {concepts?.map((c) => (
            <li key={c.id}>
              <strong>{c.name}</strong>
              <div className="meta">{c.description}</div>
            </li>
          ))}
          {concepts?.length === 0 && <EmptyState icon={Network} title="No concepts yet" hint="Ingest a document first." />}
        </ul>
      )}
    </div>
  )
}