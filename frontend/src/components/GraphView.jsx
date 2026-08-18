import { useEffect, useRef, useState } from "react"

// Minimal force-directed layout -- no graph library dependency.
// Runs a short simulation once on mount/data-change, then settles
// (matches "motion communicates state, not decoration": this
// animates while finding a layout, then stops, it doesn'"'"'t loop).
function simulateLayout(nodes, edges, width, height, iterations = 220) {
  const positioned = nodes.map((n, i) => ({
    ...n,
    x: width / 2 + Math.cos((i / nodes.length) * Math.PI * 2) * 80,
    y: height / 2 + Math.sin((i / nodes.length) * Math.PI * 2) * 80,
    vx: 0,
    vy: 0,
  }))
  const byId = Object.fromEntries(positioned.map((n) => [n.id, n]))

  for (let iter = 0; iter < iterations; iter++) {
    // repulsion between all node pairs
    for (let i = 0; i < positioned.length; i++) {
      for (let j = i + 1; j < positioned.length; j++) {
        const a = positioned[i]
        const b = positioned[j]
        const dx = a.x - b.x
        const dy = a.y - b.y
        const distSq = Math.max(dx * dx + dy * dy, 1)
        const force = 900 / distSq
        const dist = Math.sqrt(distSq)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        a.vx += fx; a.vy += fy
        b.vx -= fx; b.vy -= fy
      }
    }
    // attraction along edges
    edges.forEach((e) => {
      const a = byId[e.source_id]
      const b = byId[e.target_id]
      if (!a || !b) return
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (dist - 90) * 0.02
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      a.vx += fx; a.vy += fy
      b.vx -= fx; b.vy -= fy
    })
    // center pull + integrate + damping
    positioned.forEach((n) => {
      n.vx += (width / 2 - n.x) * 0.001
      n.vy += (height / 2 - n.y) * 0.001
      n.x += n.vx * 0.4
      n.y += n.vy * 0.4
      n.vx *= 0.85
      n.vy *= 0.85
      n.x = Math.max(24, Math.min(width - 24, n.x))
      n.y = Math.max(24, Math.min(height - 24, n.y))
    })
  }
  return positioned
}

export default function GraphView({ nodes, edges, height = 380, getNodeColor, getNodeLabel }) {
  const containerRef = useRef(null)
  const [dims, setDims] = useState({ width: 600, height })
  const [positions, setPositions] = useState([])

  useEffect(() => {
    if (containerRef.current) {
      setDims({ width: containerRef.current.clientWidth, height })
    }
  }, [height])

  useEffect(() => {
    if (nodes.length === 0) {
      setPositions([])
      return
    }
    setPositions(simulateLayout(nodes, edges, dims.width, dims.height))
  }, [nodes, edges, dims])

  const byId = Object.fromEntries(positions.map((n) => [n.id, n]))

  return (
    <div ref={containerRef} className="graph-container">
      <svg width={dims.width} height={dims.height}>
        {edges.map((e, i) => {
          const a = byId[e.source_id]
          const b = byId[e.target_id]
          if (!a || !b) return null
          return (
            <line
              key={i}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              className={`graph-edge graph-edge-${e.relationship_type}`}
            />
          )
        })}
        {positions.map((n) => (
          <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
            <circle r={n.node_type === "concept" ? 7 : 5} className={`graph-node graph-node-${n.node_type}`} />
            <text x={0} y={n.node_type === "concept" ? -12 : -10} textAnchor="middle" className="graph-node-label">
              {(getNodeLabel ? getNodeLabel(n) : n.name || n.title).slice(0, 22)}
            </text>
          </g>
        ))}
      </svg>
      {nodes.length === 0 && <div className="graph-empty hint">No graph data yet.</div>}
    </div>
  )
}