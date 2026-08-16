import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronRight, ShieldCheck, ShieldAlert } from "lucide-react"

// Every field here comes directly from the backend'"'"'s VerificationSummary
// (Reasoning + Validation + Reflection, Â§13/Â§17). Nothing is estimated
// or invented on the frontend -- this panel only formats real numbers.
export default function VerificationPanel({ verification, delivered }) {
  const [expanded, setExpanded] = useState(false)
  if (!verification) return null

  const Icon = delivered ? ShieldCheck : ShieldAlert

  return (
    <div className="verification-panel">
      <button className="verification-summary" onClick={() => setExpanded((v) => !v)}>
        <Icon size={13} strokeWidth={1.75} />
        <span>{delivered ? "VERIFIED" : "NOT VERIFIED"}</span>
        <span className="verification-confidence">
          {verification.confidence != null ? `${Math.round(verification.confidence * 100)}%` : "--"}
        </span>
        <ChevronRight size={12} className={`chevron ${expanded ? "expanded" : ""}`} />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            className="verification-detail"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
          >
            <div className="verification-row"><span>Sources checked</span><span>{verification.sources_checked}</span></div>
            <div className="verification-row"><span>Evidence items</span><span>{verification.evidence_count}</span></div>
            <div className="verification-row"><span>Divergent phrasing detected</span><span>{verification.contradictions_detected}</span></div>
            <div className="verification-row">
              <span>Source agreement</span>
              <span>{verification.agreement_score != null ? `${Math.round(verification.agreement_score * 100)}%` : "--"}</span>
            </div>
            <div className="verification-row"><span>Confidence</span><span>{verification.confidence != null ? verification.confidence.toFixed(2) : "--"}</span></div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}