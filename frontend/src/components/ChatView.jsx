import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Radio, Bot, User } from "lucide-react"
import { api } from "../api"
import CitationText from "./Citation"
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
      <h2><Bot size={20} /> Chat</h2>
      <p className="hint">
        "Send (validated)" runs the full reasoning + validation pipeline. "Send (stream preview)"
        shows live generation without the validation gate.
      </p>
      {sessionId && <p className="hint">Session: {sessionId}</p>}

      <div className="chat-log">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              className={`chat-message ${m.role}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div className="avatar">{m.role === "assistant" ? <Bot size={16} /> : <User size={16} />}</div>
              <div className="chat-body">
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
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div className="chat-message assistant" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="avatar"><Bot size={16} /></div>
            <div className="chat-body"><TypingDots /></div>
          </motion.div>
        )}

        {streaming && (
          <motion.div className="chat-message assistant streaming" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="avatar"><Radio size={16} /></div>
            <div className="chat-body">
              <p>{streamText}<span className="streaming-cursor" /></p>
            </div>
          </motion.div>
        )}
      </div>

      <textarea value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask something..." rows={3} />

      <label className="hint" style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.6rem" }}>
        <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} style={{ width: "auto", margin: 0 }} />
        Also search the internet (uses Tavily credits)
      </label>

      <div className="button-row">
        <motion.button whileTap={{ scale: 0.96 }} onClick={sendValidated} disabled={loading || streaming}>
          {loading ? <Spinner size={14} /> : <Send size={14} />} Send (validated)
        </motion.button>
        <motion.button whileTap={{ scale: 0.96 }} onClick={sendStreaming} disabled={loading || streaming}>
          <Radio size={14} /> Send (stream preview)
        </motion.button>
      </div>
    </div>
  )
}
