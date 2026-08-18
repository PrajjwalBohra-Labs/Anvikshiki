import { useState } from "react"
import { motion } from "framer-motion"
import { FlaskConical, Search as SearchIcon } from "lucide-react"
import GraphView from "./GraphView"
import { api } from "../api"
import CitationText from "./Citation"
import Toggle from "./Toggle"
import { Spinner } from "./shared"
import { useToast } from "./Toast"

export default function ResearchWorkspace() {
  const [question, setQuestion] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [useWebSearch, setUseWebSearch] = useState(false)
  const { showToast } = useToast()

  async function runResearch() {
    if (!question.trim()) return
    setLoading(true)
    try {
      setResult(await api.research(question, 5, useWebSearch))
    } catch (err) {
      showToast(err.message, "error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h2><FlaskConical size={16} strokeWidth={1.75} /> Research</h2>
      <div className="status-indicator"><span className="status-dot" /> Synthesis Engine &middot; Ready</div>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a multi-part research question..." rows={3} />
      <Toggle checked={useWebSearch} onChange={setUseWebSearch} label="Web Research" />
      <div className="button-row">
        <button className="btn-primary" onClick={runResearch} disabled={loading}>
          {loading ? <Spinner size={12} /> : <SearchIcon size={12} strokeWidth={2} />} Research
        </button>
      </div>

      {result && (
        <motion.div className="research-result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
          <h3>Sub-questions</h3>
          <ul className="list">{result.sub_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          <h3>Synthesized Answer</h3>
          <CitationText text={result.synthesized_answer} />
          {result.delivered === false && result.validation_violations?.length > 0 && (
            <details className="hint" style={{ marginTop: "0.6rem" }}>
              <summary>Why was this blocked?</summary>
              <ul>{result.validation_violations.map((v, i) => <li key={i}>{v}</li>)}</ul>
            </details>
          )}
          <h3>References ({result.references.length})</h3>
          <ul className="list">
            {result.references.map((r) => (
              <li key={r.document_id || r.url}>
                <span className={`source-badge ${r.source_type}`}>{r.source_type === "web" ? "WEB" : "LOCAL"}</span>{" "}
                {r.source_type === "web" ? <a href={r.url} target="_blank" rel="noreferrer" style={{ color: "var(--text-secondary)" }}>{r.title}</a> : r.title}
              </li>
            ))}
          </ul>

          {result.comparisons && result.comparisons.length > 0 && (
            <>
              <h3>Source Map</h3>
              <p className="hint" style={{ marginBottom: "0.6rem" }}>
                Lines show lexical overlap between sources -- muted for divergent phrasing, bright for agreement.
                Not verified semantic contradiction detection.
              </p>
              <GraphView
                nodes={Array.from(
                  new Set(result.references.map((r) => r.document_id || r.url))
                ).map((key) => {
                  const ref = result.references.find((r) => (r.document_id || r.url) === key)
                  return { id: key, name: ref.title, node_type: ref.source_type === "web" ? "document" : "concept" }
                })}
                edges={result.comparisons.map((c) => ({
                  source_id: c.source_a,
                  target_id: c.source_b,
                  relationship_type: c.relation,
                }))}
                height={260}
              />
            </>
          )}
        </motion.div>
      )}
    </div>
  )
}