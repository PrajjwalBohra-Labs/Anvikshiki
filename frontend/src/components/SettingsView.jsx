import { useState } from "react"
import { motion } from "framer-motion"
import { Settings as SettingsIcon, Save, Download } from "lucide-react"
import { api } from "../api"
import { useToast } from "./Toast"

export default function SettingsView() {
  const [key, setKey] = useState("")
  const [value, setValue] = useState("")
  const { showToast } = useToast()

  async function save() {
    if (!key.trim()) return
    await api.setSetting(key, value)
    showToast("Saved", "success")
  }

  async function load() {
    if (!key.trim()) return
    try {
      const res = await api.getSetting(key)
      setValue(res.value)
      showToast("Loaded", "info")
    } catch (err) {
      showToast(`Not found: ${err.message}`, "error")
    }
  }

  return (
    <div className="panel">
      <h2><SettingsIcon size={20} /> Settings</h2>
      <div className="button-row">
        <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="key" />
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="value" />
        <motion.button whileTap={{ scale: 0.98 }} className="btn-secondary" onClick={load}><Download size={14} /> Load</motion.button>
        <motion.button whileTap={{ scale: 0.98 }} className="btn-primary" onClick={save}><Save size={14} /> Save</motion.button>
      </div>
    </div>
  )
}
