import { useState } from "react"
import { motion } from "framer-motion"
import { FlaskConical, Search as SearchIcon } from "lucide-react"
import { api } from "../api"
import CitationText from "./Citation"
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
      <h2><FlaskConical size={20} /> Research</h2>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a multi-part research question..." rows={3} />
      <label className="hint" style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.6rem" }}>
        <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} style={{ width: "auto", margin: 0 }} />
        Also search the internet (uses Tavily credits)
      </label>
      <motion.button whileTap={{ scale: 0.96 }} onClick={runResearch} disabled={loading}>
        {loading ? <Spinner size={14} /> : <SearchIcon size={14} />} Research
      </motion.button>

      {result && (
        <motion.div className="research-result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h3>Sub-questions</h3>
          <ul>{result.sub_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          <h3>Synthesized Answer</h3>
          <CitationText text={result.synthesized_answer} />
          {result.delivered === false && result.validation_violations?.length > 0 && (
            <details className="hint" style={{ marginTop: "0.5rem" }}>
              <summary>Why was this blocked?</summary>
              <ul>{result.validation_violations.map((v, i) => <li key={i}>{v}</li>)}</ul>
            </details>
          )}
          <h3>References ({result.references.length})</h3>
          <ul>
            {result.references.map((r) => (
              <li key={r.document_id || r.url}>
                <span className={`source-badge ${r.source_type}`}>{r.source_type === "web" ? "WEB" : "LOCAL"}</span>{" "}
                {r.source_type === "web" ? <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> : r.title}
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  )
}
