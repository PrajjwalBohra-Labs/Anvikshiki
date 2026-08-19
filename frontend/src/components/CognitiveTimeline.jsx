import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, Clock } from "lucide-react"
import { api } from "../api"

// Same trace data the live Cognitive Execution Environment polls
// (§28) -- this just renders it as a static, timestamped list after
// the fact instead of a live status row. Fetched once on expand, not
// polled, since the request is already complete by the time this is
// visible.
export default function CognitiveTimeline({ traceId }) {
  const [expanded, setExpanded] = useState(false)
  const [events, setEvents] = useState(null)
  const [loading, setLoading] = useState(false)

  async function toggle() {
    const next = !expanded
    setExpanded(next)
    if (next && events === null) {
      setLoading(true)
      try {
        const data = await api.getTrace(traceId)
        setEvents(data)
      } catch {
        setEvents([])
      } finally {
        setLoading(false)
      }
    }
  }

  if (!traceId) return null

  const relevant = (events || []).filter((e) => e.event_type !== "metric")

  return (
    <div className="timeline-wrapper">
      <button className="timeline-toggle" onClick={toggle}>
        <Clock size={11} strokeWidth={1.75} />
        <span>Execution timeline</span>
        <ChevronRight size={11} className={`chevron ${expanded ? "expanded" : ""}`} />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            className="timeline-detail"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
          >
            {loading && <div className="hint" style={{ padding: "0.5rem 0" }}>Loading trace...</div>}
            {!loading && relevant.length === 0 && <div className="hint" style={{ padding: "0.5rem 0" }}>No trace events recorded.</div>}
            {!loading && relevant.map((e, i) => (
              <div key={i} className="timeline-row">
                <span className="timeline-time">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className={`timeline-stage timeline-${e.event_type}`}>{e.stage}</span>
                <span className="timeline-event-type">{e.event_type.replace("_", " ")}</span>
                {e.duration_ms != null && <span className="timeline-duration">{e.duration_ms.toFixed(0)}ms</span>}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}