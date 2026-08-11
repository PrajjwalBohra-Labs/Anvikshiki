import { useEffect, useState } from "react"
import { api } from "../api"

export default function ConceptExplorer() {
  const [concepts, setConcepts] = useState([])

  useEffect(() => { api.listConcepts().then(setConcepts) }, [])

  return (
    <div className="panel">
      <h2>Concepts</h2>
      <ul className="list">
        {concepts.map((c) => (
          <li key={c.id}>
            <strong>{c.name}</strong>
            <div className="meta">{c.description}</div>
          </li>
        ))}
        {concepts.length === 0 && <li className="hint">No concepts yet -- ingest a document first.</li>}
      </ul>
    </div>
  )
}
