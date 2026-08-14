import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  MessageSquare, FileText, Network, FlaskConical,
  History, FolderKanban, Search, Settings as SettingsIcon,
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

const TABS = {
  chat: { label: "Chat", icon: MessageSquare, component: ChatView },
  documents: { label: "Documents", icon: FileText, component: DocumentBrowser },
  concepts: { label: "Concepts", icon: Network, component: ConceptExplorer },
  research: { label: "Research", icon: FlaskConical, component: ResearchWorkspace },
  history: { label: "Session History", icon: History, component: SessionHistory },
  projects: { label: "Projects", icon: FolderKanban, component: ProjectWorkspace },
  search: { label: "Search", icon: Search, component: SearchView },
  settings: { label: "Settings", icon: SettingsIcon, component: SettingsView },
}

export default function App() {
  const [active, setActive] = useState("chat")
  const ActiveComponent = TABS[active].component

  return (
    <ToastProvider>
      <div className="mandala-watermark" aria-hidden="true" />
      <div className="app">
        <header className="app-header">
          <img src="/anvikshiki-logo-40.png" alt="" className="app-logo" />
          <div>
            <h1>Anvikshiki</h1>
            <p className="tagline">
              A modular cognitive architecture.
            </p>
          </div>
        </header>

        <nav>
          {Object.entries(TABS).map(([key, tab]) => {
            const Icon = tab.icon
            const isActive = key === active
            return (
              <button key={key} className={isActive ? "active" : ""} onClick={() => setActive(key)}>
                {isActive && (
                  <motion.div className="nav-pill" layoutId="nav-pill" transition={{ duration: 0.2, ease: "easeOut" }} />
                )}
                <Icon size={14} strokeWidth={1.75} style={{ position: "relative", zIndex: 1 }} />
                <span style={{ position: "relative", zIndex: 1 }}>{tab.label}</span>
              </button>
            )
          })}
        </nav>

        <AnimatePresence mode="wait">
          <motion.main
            key={active}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <ActiveComponent />
          </motion.main>
        </AnimatePresence>
      </div>
    </ToastProvider>
  )
}