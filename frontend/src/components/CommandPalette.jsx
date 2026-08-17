import { useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Search, CornerDownLeft } from "lucide-react"

// Every entry here is a real navigation target -- the same ALL_ITEMS
// list the sidebar renders from. No invented actions.
export default function CommandPalette({ isOpen, onClose, items, onSelect }) {
  const [query, setQuery] = useState("")
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter((item) => item.label.toLowerCase().includes(q) || item.key.includes(q))
  }, [query, items])

  useEffect(() => {
    if (isOpen) {
      setQuery("")
      setHighlighted(0)
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [isOpen])

  useEffect(() => {
    setHighlighted(0)
  }, [query])

  function handleKeyDown(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setHighlighted((h) => Math.max(h - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      const item = filtered[highlighted]
      if (item) {
        onSelect(item.key)
      }
    } else if (e.key === "Escape") {
      onClose()
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="palette-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
        >
          <motion.div
            className="palette-panel"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="palette-input-row">
              <Search size={14} strokeWidth={1.75} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="What do you want Anvikshiki to do?"
                className="palette-input"
              />
              <span className="palette-kbd">ESC</span>
            </div>

            <div className="palette-results">
              {filtered.length === 0 && <div className="palette-empty">No matching destination.</div>}
              {filtered.map((item, i) => {
                const Icon = item.icon
                return (
                  <button
                    key={item.key}
                    className={`palette-result ${i === highlighted ? "highlighted" : ""}`}
                    onMouseEnter={() => setHighlighted(i)}
                    onClick={() => onSelect(item.key)}
                  >
                    <Icon size={14} strokeWidth={1.75} />
                    <span>{item.label}</span>
                    {i === highlighted && <CornerDownLeft size={12} className="palette-enter-icon" />}
                  </button>
                )
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}