export default function MemoryPanel({ count, sources }) {
  const visible = sources.length > 0

  return (
    <div className="memory-panel">
      <div className="memory-panel__header">
        <span>{"▸"} ARCHIVE</span>
        <span className="mono">{count}</span>
      </div>

      <div className="memory-panel__stats">
        <div className="stat-row">
          <span className="stat-row__label">Documents</span>
          <span className="stat-row__value mono">{count}</span>
        </div>
        <div className="stat-row">
          <span className="stat-row__label">Sources</span>
          <span className="stat-row__value mono">{new Set(sources).size}</span>
        </div>
      </div>

      {visible && (
        <div className="memory-panel__sources">
          {sources.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-link"
              title={url}
            >
              <span className="source-link__num">{String(i + 1).padStart(2, '0')}</span>
              <span className="source-link__url">{url.replace(/^https?:\/\//, '')}</span>
            </a>
          ))}
        </div>
      )}

      {!visible && count === 0 && (
        <div className="memory-panel__empty">No documents filed yet.</div>
      )}
    </div>
  )
}
