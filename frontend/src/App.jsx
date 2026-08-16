import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  MessageSquare, FlaskConical, Network, FileText,
  FolderKanban, History, Search, Settings as SettingsIcon,
  ChevronLeft, ChevronRight,
} from "lucide-react"
import ChatView from "./components/ChatView"
import DocumentBrowser from "./components/DocumentBrowser"
import ConceptExplorer from "./components/ConceptExplorer"
import ResearchWorkspace from "./components/ResearchWorkspace"
import SessionHistory from "./components/SessionHistory"
import ProjectWorkspace from "./components/ProjectWorkspace"
import SettingsView from "./components/SettingsView"
import SearchView from "./components/SearchView"
import { ToastProvider } from "./components/Toast"

// Grouping mirrors the app'"'"'s real structure: Workspace = where you
// interact with the cognitive engine, Knowledge = what it knows,
// Projects = organizational scope, System = introspection/config.
// (No "Memory" entry -- the seven memory tiers exist server-side but
// have no dedicated browsable page yet, so it'"'"'s not listed here.)
const SECTIONS = [
  {
    label: "Workspace",
    items: [
      { key: "chat", label: "Chat", icon: MessageSquare, component: ChatView },
      { key: "research", label: "Research", icon: FlaskConical, component: ResearchWorkspace },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { key: "concepts", label: "Concepts", icon: Network, component: ConceptExplorer },
      { key: "documents", label: "Documents", icon: FileText, component: DocumentBrowser },
    ],
  },
  {
    label: "Projects",
    items: [
      { key: "projects", label: "Projects", icon: FolderKanban, component: ProjectWorkspace },
    ],
  },
  {
    label: "System",
    items: [
      { key: "history", label: "Session History", icon: History, component: SessionHistory },
      { key: "search", label: "Search", icon: Search, component: SearchView },
      { key: "settings", label: "Settings", icon: SettingsIcon, component: SettingsView },
    ],
  },
]

const ALL_ITEMS = SECTIONS.flatMap((s) => s.items)

export default function App() {
  const [active, setActive] = useState("chat")
  const [collapsed, setCollapsed] = useState(false)
  const ActiveComponent = ALL_ITEMS.find((item) => item.key === active).component

  return (
    <ToastProvider>
      <div className="mandala-watermark" aria-hidden="true" />
      <div className="app">
        <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
          <div className="sidebar-header">
            <img src="/anvikshiki-logo-32.png" alt="" className="sidebar-logo" />
            {!collapsed && <span className="sidebar-wordmark">ANVIKSHIKI</span>}
          </div>

          <nav className="sidebar-nav">
            {SECTIONS.map((section) => (
              <div className="nav-section" key={section.label}>
                {!collapsed && <div className="nav-section-label">{section.label}</div>}
                {section.items.map((item) => {
                  const Icon = item.icon
                  const isActive = item.key === active
                  return (
                    <button
                      key={item.key}
                      className={`sidebar-nav-btn ${isActive ? "active" : ""}`}
                      onClick={() => setActive(item.key)}
                      title={item.label}
                    >
                      {isActive && (
                        <motion.div
                          className="nav-pill"
                          layoutId="nav-pill"
                          transition={{ duration: 0.2, ease: "easeOut" }}
                        />
                      )}
                      <Icon size={15} strokeWidth={1.75} />
                      {!collapsed && <span>{item.label}</span>}
                    </button>
                  )
                })}
              </div>
            ))}
          </nav>

          <button className="sidebar-collapse-toggle" onClick={() => setCollapsed((v) => !v)}>
            {collapsed ? (
              <ChevronRight size={14} />
            ) : (
              <>
                <ChevronLeft size={14} />
                <span>Collapse</span>
              </>
            )}
          </button>
        </aside>

        <main className="main-content">
          <div className="main-content-inner">
            <AnimatePresence mode="wait">
              <motion.div
                key={active}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
              >
                <ActiveComponent />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </ToastProvider>
  )
}