import { useState } from "react"
import { api } from "../api"

export default function SessionHistory() {
  const [sessionId, setSessionId] = useState("")
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)

  async function load() {
    if (!sessionId.trim()) return
    setError(null)
    try {
      setHistory(await api.getSessionHistory(sessionId))
    } catch (err) {
      setError(err.message)
      setHistory([])
    }
  }

  return (
    <div className="panel">
      <h2>Session History</h2>
      <p className="hint">Paste a session ID from the Chat tab to view its turn history.</p>
      <div className="button-row">
        <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} placeholder="session id" />
        <button onClick={load}>Load</button>
      </div>
      {error && <div className="error">{error}</div>}
      <ul className="list">
        {history.map((turn) => (
          <li key={turn.question_id}>
            <strong>Q:</strong> {turn.question_text}
            <br />
            <strong>A:</strong> {turn.answer_text || "(not delivered)"}
          </li>
        ))}
      </ul>
    </div>
  )
}
