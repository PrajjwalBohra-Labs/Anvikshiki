import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { FileText, Upload } from "lucide-react"
import { api } from "../api"
import { EmptyState, Skeleton, Spinner } from "./shared"
import { useToast } from "./Toast"

export default function DocumentBrowser() {
  const [documents, setDocuments] = useState(null)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const { showToast } = useToast()

  async function refresh() {
    setDocuments(await api.listDocuments())
  }

  useEffect(() => { refresh() }, [])

  async function upload() {
    if (!file) return
    setUploading(true)
    try {
      await api.uploadDocument(file)
      showToast("Document ingested", "success")
      setFile(null)
      refresh()
    } catch (err) {
      showToast(err.message, "error")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="panel">
      <h2><FileText size={20} /> Documents</h2>
      <div className="button-row">
        <input type="file" onChange={(e) => setFile(e.target.files[0])} style={{ width: "auto" }} />
        <motion.button whileTap={{ scale: 0.96 }} onClick={upload} disabled={!file || uploading}>
          {uploading ? <Spinner size={14} /> : <Upload size={14} />} Upload &amp; Ingest
        </motion.button>
      </div>
      <ul className="list">
        {documents === null && [1, 2].map((i) => <li key={i}><Skeleton height="1.4rem" /></li>)}
        {documents?.map((doc, i) => (
          <motion.li key={doc.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <strong>{doc.title}</strong>
            <div className="meta">{doc.id}</div>
          </motion.li>
        ))}
        {documents?.length === 0 && <EmptyState icon={FileText} title="No documents yet" hint="Upload one above to get started." />}
      </ul>
    </div>
  )
}
