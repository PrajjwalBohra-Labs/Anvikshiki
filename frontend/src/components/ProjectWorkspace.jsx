import { useEffect, useState } from "react"
import { api } from "../api"

export default function ProjectWorkspace() {
  const [projects, setProjects] = useState([])
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  async function refresh() {
    setProjects(await api.listProjects())
  }

  useEffect(() => { refresh() }, [])

  async function create() {
    if (!name.trim()) return
    await api.createProject(name, description)
    setName("")
    setDescription("")
    refresh()
  }

  return (
    <div className="panel">
      <h2>Projects</h2>
      <div className="button-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" />
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" />
        <button onClick={create} disabled={!name.trim()}>Create</button>
      </div>
      <ul className="list">
        {projects.map((p) => (
          <li key={p.id}><strong>{p.name}</strong><div className="meta">{p.description}</div></li>
        ))}
        {projects.length === 0 && <li className="hint">No projects yet.</li>}
      </ul>
    </div>
  )
}
