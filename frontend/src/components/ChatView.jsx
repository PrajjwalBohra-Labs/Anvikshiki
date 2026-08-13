import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Radio, Bot, User } from "lucide-react"
import { api } from "../api"
import CitationText from "./Citation"
import Toggle from "./Toggle"
import { TypingDots, Spinner } from "./shared"
import { useToast } from "./Toast"

export default function ChatView() {
  const [query, setQuery] = useState("")
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const [loading, setLoading] = useState(false)
  const [useWebSearch, setUseWebSearch] = useState(false)
  const { showToast } = useToast()

  async function sendValidated() {
    if (!query.trim()) return
    setLoading(true)
    const userQuery = query
    setMessages((prev) => [...prev, { role: "user", text: userQuery }])
    setQuery("")
    try {
      const result = await api.chat(userQuery, sessionId, useWebSearch)
      setSessionId(result.session_id)
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: result.response, delivered: result.delivered, confidence: result.confidence },
      ])
      if (!result.delivered) showToast("Response was not delivered -- failed validation", "error")
    } catch (err) {
      showToast(err.message, "error")
    } finally {
      setLoading(false)
    }
  }

  async function sendStreaming() {
    if (!query.trim()) return
    setStreaming(true)
    setStreamText("")
    const userQuery = query
    setQuery("")
    try {
      await api.chatStream(userQuery, (token) => setStreamText((prev) => prev + token), () => setStreaming(false))
    } catch (err) {
      showToast(err.message, "error")
      setStreaming(false)
    }
  }

  return (
    <div className="panel">
      <h2><Bot size={16} strokeWidth={1.75} /> Chat</h2>
      <div className="status-indicator"><span className="status-dot" /> Cognitive Engine &middot; Ready</div>
      <p className="hint" style={{ marginBottom: "1rem" }}>
        Validated runs the full reasoning and verification pipeline. Stream shows live generation without the validation gate.
      </p>
      {sessionId && <p className="meta" style={{ marginBottom: "1rem" }}>SESSION {sessionId}</p>}

      <div className="chat-log">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              className={`chat-message ${m.role}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="avatar">{m.role === "assistant" ? <Bot size={13} strokeWidth={1.75} /> : <User size={13} strokeWidth={1.75} />}</div>
              <div className="chat-body">
                {m.role === "assistant" ? (
                  <>
                    <CitationText text={m.text} />
                    <div className="meta" style={{ marginTop: "0.4rem" }}>
                      {m.delivered ? `CONFIDENCE ${m.confidence?.toFixed(2)}` : "NOT DELIVERED -- VALIDATION FAILED"}
                    </div>
                  </>
                ) : (
                  <p>{m.text}</p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div className="chat-message assistant" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="avatar"><Bot size={13} strokeWidth={1.75} /></div>
            <div className="chat-body"><TypingDots /></div>
          </motion.div>
        )}

        {streaming && (
          <motion.div className="chat-message assistant streaming" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="avatar"><Radio size={13} strokeWidth={1.75} /></div>
            <div className="chat-body">
              <p>{streamText}<span className="streaming-cursor" /></p>
            </div>
          </motion.div>
        )}
      </div>

      <textarea value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask the cognitive engine..." rows={3} />

      <Toggle checked={useWebSearch} onChange={setUseWebSearch} label="Web Research" />

      <div className="button-row">
        <button className="btn-primary" onClick={sendValidated} disabled={loading || streaming}>
          {loading ? <Spinner size={12} /> : <Send size={12} strokeWidth={2} />} Send &middot; Validated
        </button>
        <button className="btn-secondary" onClick={sendStreaming} disabled={loading || streaming}>
          <Radio size={12} strokeWidth={2} /> Send &middot; Stream
        </button>
      </div>
    </div>
  )
}