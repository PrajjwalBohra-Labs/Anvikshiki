import { useState } from "react"
import ChatView from "./components/ChatView"
import DocumentBrowser from "./components/DocumentBrowser"
import ConceptExplorer from "./components/ConceptExplorer"
import ResearchWorkspace from "./components/ResearchWorkspace"
import SessionHistory from "./components/SessionHistory"
import ProjectWorkspace from "./components/ProjectWorkspace"
import SettingsView from "./components/SettingsView"
import SearchView from "./components/SearchView"

const TABS = {
  chat: { label: "Chat", component: ChatView },
  documents: { label: "Documents", component: DocumentBrowser },
  concepts: { label: "Concepts", component: ConceptExplorer },
  research: { label: "Research", component: ResearchWorkspace },
  history: { label: "Session History", component: SessionHistory },
  projects: { label: "Projects", component: ProjectWorkspace },
  search: { label: "Search", component: SearchView },
  settings: { label: "Settings", component: SettingsView },
}

export default function App() {
  const [active, setActive] = useState("chat")
  const ActiveComponent = TABS[active].component

  return (
    <div className="app">
      <header>
        <h1>Anvikshiki</h1>
        <p className="tagline">
          A modular cognitive architecture -- this UI only renders results; all reasoning happens on the backend.
        </p>
      </header>
      <nav>
        {Object.entries(TABS).map(([key, tab]) => (
          <button key={key} className={key === active ? "active" : ""} onClick={() => setActive(key)}>
            {tab.label}
          </button>
        ))}
      </nav>
      <main>
        <ActiveComponent />
      </main>
    </div>
  )
}
