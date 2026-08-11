import { useEffect, useState } from "react"
import { api } from "../api"

export default function DocumentBrowser() {
  const [documents, setDocuments] = useState([])
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState("")

  async function refresh() {
    setDocuments(await api.listDocuments())
  }

  useEffect(() => { refresh() }, [])

  async function upload() {
    if (!file) return
    setStatus("Uploading and ingesting...")
    try {
      await api.uploadDocument(file)
      setStatus("Ingested.")
      setFile(null)
      refresh()
    } catch (err) {
      setStatus(`Failed: ${err.message}`)
    }
  }

  return (
    <div className="panel">
      <h2>Documents</h2>
      <div className="button-row">
        <input type="file" onChange={(e) => setFile(e.target.files[0])} />
        <button onClick={upload} disabled={!file}>Upload &amp; Ingest</button>
      </div>
      {status && <p className="hint">{status}</p>}
      <ul className="list">
        {documents.map((doc) => (
          <li key={doc.id}>
            <strong>{doc.title}</strong>
            <div className="meta">{doc.id}</div>
          </li>
        ))}
        {documents.length === 0 && <li className="hint">No documents yet.</li>}
      </ul>
    </div>
  )
}
