import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { FolderKanban, Plus } from "lucide-react"
import { api } from "../api"
import { EmptyState, Skeleton } from "./shared"
import { useToast } from "./Toast"

export default function ProjectWorkspace() {
  const [projects, setProjects] = useState(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const { showToast } = useToast()

  async function refresh() {
    setProjects(await api.listProjects())
  }

  useEffect(() => { refresh() }, [])

  async function create() {
    if (!name.trim()) return
    try {
      await api.createProject(name, description)
      showToast("Project created", "success")
      setName(""); setDescription("")
      refresh()
    } catch (err) {
      showToast(err.message, "error")
    }
  }

  return (
    <div className="panel">
      <h2><FolderKanban size={20} /> Projects</h2>
      <div className="button-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" />
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" />
        <motion.button whileTap={{ scale: 0.98 }} className="btn-primary" onClick={create} disabled={!name.trim()}>
          <Plus size={14} /> Create
        </motion.button>
      </div>
      <ul className="list">
        {projects === null && [1, 2].map((i) => <li key={i}><Skeleton height="1.4rem" /></li>)}
        {projects?.map((p, i) => (
          <motion.li key={p.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <strong>{p.name}</strong>
            <div className="meta">{p.description}</div>
          </motion.li>
        ))}
        {projects?.length === 0 && <EmptyState icon={FolderKanban} title="No projects yet" />}
      </ul>
    </div>
  )
}
