// Renders response text with [Source Name] citations styled
// distinctly. Pure display formatting -- it does not interpret,
// verify, or reason about the citations, just highlights text the
// backend already produced.
export default function CitationText({ text }) {
  if (!text) return null
  const parts = text.split(/(\[[^\]]+\])/g)
  return (
    <p className="citation-text">
      {parts.map((part, i) =>
        /^\[[^\]]+\]$/.test(part) ? (
          <span key={i} className="citation-badge">{part}</span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  )
}
