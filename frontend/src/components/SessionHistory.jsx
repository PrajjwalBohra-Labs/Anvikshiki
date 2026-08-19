import { useState } from "react"
import { motion } from "framer-motion"
import { History, ChevronRight } from "lucide-react"
import { api } from "../api"
import { EmptyState, Spinner } from "./shared"
import { useToast } from "./Toast"

export default function SessionHistory() {
  const [sessionId, setSessionId] = useState("")
  const [history, setHistory] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()

  async function load() {
    if (!sessionId.trim()) return
    setLoading(true)
    try {
      const [historyResult, summaryResult] = await Promise.all([
        api.getSessionHistory(sessionId),
        api.getSessionSummary(sessionId),
      ])
      setHistory(historyResult)
      setSummary(summaryResult)
    } catch (err) {
      showToast(err.message, "error")
      setHistory(null)
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h2><History size={20} strokeWidth={1.75} /> Session History</h2>
      <p className="hint">Paste a session ID from the Chat tab to view its record.</p>
      <div className="button-row">
        <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} placeholder="session id" />
        <motion.button whileTap={{ scale: 0.98 }} className="btn-primary" onClick={load} disabled={loading}>
          {loading ? <Spinner size={14} /> : <ChevronRight size={14} />} Load
        </motion.button>
      </div>

      {summary && (
        <motion.div className="session-summary-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="session-summary-grid">
            <div className="session-stat"><span className="session-stat-value">{summary.message_count}</span><span className="session-stat-label">Messages</span></div>
            <div className="session-stat"><span className="session-stat-value">{summary.verified_count}</span><span className="session-stat-label">Verified</span></div>
            <div className="session-stat"><span className="session-stat-value">{summary.source_count}</span><span className="session-stat-label">Sources</span></div>
            <div className="session-stat"><span className="session-stat-value">{summary.concept_count}</span><span className="session-stat-label">Concepts</span></div>
          </div>
        </motion.div>
      )}

      <ul className="list">
        {history?.map((turn, i) => (
          <motion.li key={turn.question_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <strong>Q:</strong> {turn.question_text}<br />
            <strong>A:</strong> {turn.answer_text || "(not delivered)"}
          </motion.li>
        ))}
        {history?.length === 0 && <EmptyState icon={History} title="No turns in this session yet" />}
      </ul>
    </div>
  )
}