import { useState } from "react"
import { api } from "../api"

export default function SettingsView() {
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const [status, setStatus] = useState("")

  async function save() {
    if (!key.trim()) return
    await api.setSetting(key, value)
    setStatus("Saved.")
  }

  async function load() {
    if (!key.trim()) return
    try {
      const res = await api.getSetting(key)
      setValue(res.value)
      setStatus("Loaded.")
    } catch (err) {
      setStatus(`Not found: ${err.message}`)
    }
  }

  return (
    <div className="panel">
      <h2>Settings</h2>
      <div className="button-row">
        <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="key" />
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="value" />
        <button onClick={load}>Load</button>
        <button onClick={save}>Save</button>
      </div>
      {status && <p className="hint">{status}</p>}
    </div>
  )
}
