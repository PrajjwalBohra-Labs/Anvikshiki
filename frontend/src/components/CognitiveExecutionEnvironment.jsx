import { useEffect, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { api } from "../api"

const STAGES = [
  { key: "interpret", label: "Interpret" },
  { key: "retrieve", label: "Retrieve" },
  { key: "reason", label: "Reason" },
  { key: "generate", label: "Generate" },
  { key: "verify", label: "Verify" },
  { key: "reflect", label: "Reflect" },
]

function deriveStageStates(events) {
  const started = new Set(events.filter((e) => e.event_type === "stage_start").map((e) => e.stage))
  const ended = new Set(events.filter((e) => e.event_type === "stage_end").map((e) => e.stage))
  const failed = new Set(events.filter((e) => e.event_type === "failure").map((e) => e.stage))

  return STAGES.map((stage) => {
    let status = "pending"
    if (failed.has(stage.key)) status = "failed"
    else if (ended.has(stage.key)) status = "done"
    else if (started.has(stage.key)) status = "active"
    return { ...stage, status }
  })
}

// Polls the real trace store (§28) every 200ms while a request is in
// flight -- every stage shown here is a genuine recorded event, not
// a simulated animation timed to guess when things finish.
export default function CognitiveExecutionEnvironment({ traceId, active }) {
  const [stages, setStages] = useState(deriveStageStates([]))
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!active || !traceId) {
      setStages(deriveStageStates([]))
      return
    }

    let cancelled = false
    async function poll() {
      try {
        const events = await api.getTrace(traceId)
        if (!cancelled) setStages(deriveStageStates(events))
      } catch {
        // trace not found yet / transient -- keep polling silently
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 200)
    return () => {
      cancelled = true
      clearInterval(intervalRef.current)
    }
  }, [traceId, active])

  if (!active) return null

  return (
    <motion.div
      className="cee-panel"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="cee-label">Cognitive Engine</div>
      <div className="cee-stages">
        {stages.map((stage, i) => (
          <div key={stage.key} className="cee-stage-row">
            <span className={`cee-dot cee-dot-${stage.status}`} />
            <span className={`cee-stage-name cee-stage-${stage.status}`}>{stage.label}</span>
            {i < stages.length - 1 && <span className="cee-connector" />}
          </div>
        ))}
      </div>
    </motion.div>
  )
}