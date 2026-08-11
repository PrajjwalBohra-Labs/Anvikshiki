import { useState } from "react"
import { api } from "../api"

export default function SearchView() {
  const [q, setQ] = useState("")
  const [results, setResults] = useState([])
  const [error, setError] = useState(null)

  async function runSearch() {
    if (!q.trim()) return
    setError(null)
    try {
      const res = await api.search(q)
      setResults(res.results)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>Search</h2>
      <div className="button-row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search knowledge base..." />
        <button onClick={runSearch}>Search</button>
      </div>
      {error && <div className="error">{error}</div>}
      <ul className="list">
        {results.map((r) => (
          <li key={r.chunk_id}>
            <strong>{r.document_title}</strong> (score {r.score.toFixed(2)})
            <div className="meta">{r.chunk_text}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
