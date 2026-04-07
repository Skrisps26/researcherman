import ReactMarkdown from 'react-markdown'
import { useState } from 'react'

export default function ReportViewer({ report }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(report)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'research-report.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!report) {
    return (
      <div className="report-empty">
        <div className="report-empty__icon">◎</div>
        <h2 className="report-empty__title">No Report Generated</h2>
        <p className="report-empty__desc">
          Submit a research question via the intake panel to begin an investigation.
        </p>
        <div className="report-empty__steps">
          <div className="report-empty__step">1 {"—"} Enter question</div>
          <div className="report-empty__step">2 {"—"} Agents search {"&"} analyze</div>
          <div className="report-empty__step">3 {"—"} Report appears here</div>
        </div>
      </div>
    )
  }

  return (
    <div className="report-viewer">
      <div className="report-viewer__bar">
        <span className="report-viewer__title">◎ REPORT</span>
        <div className="report-viewer__actions">
          <button onClick={handleCopy} className={"report-btn " + (copied ? 'report-btn--copied' : '')}>
            {copied ? '✓ COPIED' : 'COPY'}
          </button>
          <button onClick={handleDownload} className="report-btn report-btn--download">
            <span>{"↓"}</span> DOWNLOAD
          </button>
        </div>
      </div>

      <div className="report-viewer__content">
        <div className="report-stamp" aria-hidden="true">
          <div className="report-stamp__border">
            <span>RESEARCH REPORT</span>
          </div>
        </div>
        <div className="prose">
          <ReactMarkdown>{report}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
