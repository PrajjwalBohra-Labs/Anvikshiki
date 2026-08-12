import { motion } from "framer-motion"
import { Loader2 } from "lucide-react"

export function Card({ children, className = "", ...props }) {
  return (
    <motion.div
      className={`ui-card ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export function EmptyState({ icon: Icon, title, hint }) {
  return (
    <motion.div className="empty-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {Icon && <Icon size={32} strokeWidth={1.5} />}
      <p className="empty-state-title">{title}</p>
      {hint && <p className="empty-state-hint">{hint}</p>}
    </motion.div>
  )
}

export function Skeleton({ width = "100%", height = "1rem" }) {
  return <div className="skeleton" style={{ width, height }} />
}

export function Spinner({ size = 16 }) {
  return <Loader2 size={size} className="spinner" />
}

export function TypingDots() {
  return (
    <div className="typing-dots">
      <span /><span /><span />
    </div>
  )
}
