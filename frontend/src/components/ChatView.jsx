import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Radio, Bot, User } from "lucide-react"
import { api } from "../api"
import CitationText from "./Citation"
import Toggle from "./Toggle"
import CognitiveExecutionEnvironment from "./CognitiveExecutionEnvironment"
import CognitiveTimeline from "./CognitiveTimeline"
import VerificationPanel from "./VerificationPanel"
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
  const [activeTraceId, setActiveTraceId] = useState(null)
  const { showToast } = useToast()

  async function sendValidated() {
    if (!query.trim()) return
    const traceId = crypto.randomUUID()
    setActiveTraceId(traceId)
    setLoading(true)
    const userQuery = query
    setMessages((prev) => [...prev, { role: "user", text: userQuery }])
    setQuery("")
    try {
      const result = await api.chat(userQuery, sessionId, useWebSearch, traceId)
      setSessionId(result.session_id)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: result.response,
          delivered: result.delivered,
          confidence: result.confidence,
          verification: result.verification,
          context: result.context,
          traceId,
        },
      ])
      if (!result.delivered) showToast("Response was not delivered -- failed validation", "error")
    } catch (err) {
      showToast(err.message, "error")
    } finally {
      setLoading(false)
      // keep the trace panel visible briefly so the final "done" states register,
      // then let it collapse on the next send
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
    <div className="panel chat-command-panel">
      <div className="status-indicator"><span className="status-dot" /> Cognitive Engine &middot; Ready</div>
      <h2 className="ask-heading">Ask Anvikshiki</h2>

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
                    {m.context && (
                      <div className="context-line">
                        Context assembled &middot; {m.context.retrieved_chunk_count} chunks &middot;{" "}
                        {m.context.document_count} documents &middot; {m.context.concept_relationship_count} relationships
                      </div>
                    )}
                    <CitationText text={m.text} />
                    <VerificationPanel verification={m.verification} delivered={m.delivered} />
                    <CognitiveTimeline traceId={m.traceId} />
                  </>
                ) : (
                  <p>{m.text}</p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {(loading || activeTraceId) && !streaming && (
            <CognitiveExecutionEnvironment traceId={activeTraceId} active={loading} />
          )}
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

      {sessionId && <p className="meta" style={{ marginBottom: "0.6rem" }}>SESSION {sessionId}</p>}

      <div className="command-surface">
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask the cognitive engine..." rows={3} />
        <div className="command-controls">
          <Toggle checked={useWebSearch} onChange={setUseWebSearch} label="Web Research" />
          <div className="button-row">
            <button className="btn-secondary" onClick={sendStreaming} disabled={loading || streaming}>
              <Radio size={12} strokeWidth={2} /> Send &middot; Stream
            </button>
            <button className="btn-primary" onClick={sendValidated} disabled={loading || streaming}>
              {loading ? <Spinner size={12} /> : <Send size={12} strokeWidth={2} />} Send &middot; Validated
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}