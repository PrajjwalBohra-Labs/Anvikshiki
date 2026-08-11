import { useState } from "react"
import { api } from "../api"
import CitationText from "./Citation"

export default function ResearchWorkspace() {
  const [question, setQuestion] = useState("")
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [useWebSearch, setUseWebSearch] = useState(false)

  async function runResearch() {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    try {
      setResult(await api.research(question, 5, useWebSearch))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h2>Research</h2>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a multi-part research question..." rows={3} />
      <label className="hint" style={{ display: "block", margin: "0.5rem 0" }}>
        <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} />
        {" "}Also search the internet (uses Tavily credits)
      </label>
      <button onClick={runResearch} disabled={loading}>Research</button>
      {error && <div className="error">{error}</div>}
      {result && (
        <div className="research-result">
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
                <span className={`source-badge ${r.source_type}`}>
                  {r.source_type === "web" ? "WEB" : "LOCAL"}
                </span>{" "}
                {r.source_type === "web" ? (
                  <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                ) : (
                  r.title
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}



