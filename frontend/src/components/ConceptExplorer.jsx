import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Network } from "lucide-react"
import { api } from "../api"
import { EmptyState, Skeleton } from "./shared"

export default function ConceptExplorer() {
  const [concepts, setConcepts] = useState(null)

  useEffect(() => { api.listConcepts().then(setConcepts) }, [])

  return (
    <div className="panel">
      <h2><Network size={20} /> Concepts</h2>
      <ul className="list">
        {concepts === null && [1, 2].map((i) => <li key={i}><Skeleton height="1.4rem" /></li>)}
        {concepts?.map((c, i) => (
          <motion.li key={c.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <strong>{c.name}</strong>
            <div className="meta">{c.description}</div>
          </motion.li>
        ))}
        {concepts?.length === 0 && <EmptyState icon={Network} title="No concepts yet" hint="Ingest a document first." />}
      </ul>
    </div>
  )
}
