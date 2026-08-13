import { useState } from "react"
import { motion } from "framer-motion"
import { Search as SearchIcon } from "lucide-react"
import { api } from "../api"
import { EmptyState, Spinner } from "./shared"
import { useToast } from "./Toast"

export default function SearchView() {
  const [q, setQ] = useState("")
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()

  async function runSearch() {
    if (!q.trim()) return
    setLoading(true)
    try {
      const res = await api.search(q)
      setResults(res.results)
    } catch (err) {
      showToast(err.message, "error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h2><SearchIcon size={20} /> Search</h2>
      <div className="button-row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search knowledge base..." />
        <motion.button whileTap={{ scale: 0.98 }} className="btn-primary" onClick={runSearch} disabled={loading}>
          {loading ? <Spinner size={14} /> : <SearchIcon size={14} />} Search
        </motion.button>
      </div>
      <ul className="list">
        {results?.map((r, i) => (
          <motion.li key={r.chunk_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <strong>{r.document_title}</strong> <span className="meta">score {r.score.toFixed(2)}</span>
            <div className="meta">{r.chunk_text}</div>
          </motion.li>
        ))}
        {results?.length === 0 && <EmptyState icon={SearchIcon} title="No results" />}
      </ul>
    </div>
  )
}
