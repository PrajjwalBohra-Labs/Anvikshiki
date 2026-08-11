import { useState } from "react"
import { api } from "../api"
import CitationText from "./Citation"

export default function ChatView() {
  const [query, setQuery] = useState("")
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [useWebSearch, setUseWebSearch] = useState(false)

  async function sendValidated() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.chat(query, sessionId, useWebSearch)
      setSessionId(result.session_id)
      setMessages((prev) => [
        ...prev,
        { role: "user", text: query },
        { role: "assistant", text: result.response, delivered: result.delivered, confidence: result.confidence },
      ])
      setQuery("")
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function sendStreaming() {
    if (!query.trim()) return
    setStreaming(true)
    setStreamText("")
    setError(null)
    const userQuery = query
    setQuery("")
    try {
      await api.chatStream(
        userQuery,
        (token) => setStreamText((prev) => prev + token),
        () => setStreaming(false),
      )
    } catch (err) {
      setError(err.message)
      setStreaming(false)
    }
  }

  return (
    <div className="panel">
      <h2>Chat</h2>
      <p className="hint">
        "Send (validated)" runs the full reasoning + validation pipeline. "Send (stream preview)"
        shows live generation without the validation gate -- a documented tradeoff from Step 13.
      </p>
      {sessionId && <p className="hint">Session: {sessionId}</p>}
      <div className="chat-log">
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            {m.role === "assistant" ? (
              <>
                <CitationText text={m.text} />
                <div className="meta">
                  {m.delivered ? `confidence ${m.confidence?.toFixed(2)}` : "not delivered (failed validation)"}
                </div>
              </>
            ) : (
              <p>{m.text}</p>
            )}
          </div>
        ))}
        {streaming && (
          <div className="chat-message assistant streaming">
            <CitationText text={streamText} />
          </div>
        )}
      </div>
      {error && <div className="error">{error}</div>}
      <textarea value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask something..." rows={3} />
      <label className="hint" style={{ display: "block", marginBottom: "0.5rem" }}>
        <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} />
        {" "}Also search the internet (uses Tavily credits)
      </label>
      <div className="button-row">
        <button onClick={sendValidated} disabled={loading || streaming}>Send (validated)</button>
        <button onClick={sendStreaming} disabled={loading || streaming}>Send (stream preview)</button>
      </div>
    </div>
  )
}

