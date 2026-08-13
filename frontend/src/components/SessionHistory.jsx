import { useState } from "react"
import { motion } from "framer-motion"
import { History, ChevronRight } from "lucide-react"
import { api } from "../api"
import { EmptyState, Spinner } from "./shared"
import { useToast } from "./Toast"

export default function SessionHistory() {
  const [sessionId, setSessionId] = useState("")
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(false)
  const { showToast } = useToast()

  async function load() {
    if (!sessionId.trim()) return
    setLoading(true)
    try {
      setHistory(await api.getSessionHistory(sessionId))
    } catch (err) {
      showToast(err.message, "error")
      setHistory(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h2><History size={20} /> Session History</h2>
      <p className="hint">Paste a session ID from the Chat tab to view its turn history.</p>
      <div className="button-row">
        <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} placeholder="session id" />
        <motion.button whileTap={{ scale: 0.98 }} className="btn-primary" onClick={load} disabled={loading}>
          {loading ? <Spinner size={14} /> : <ChevronRight size={14} />} Load
        </motion.button>
      </div>
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
