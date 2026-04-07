import { useState, useCallback, useRef, useEffect } from 'react'
import QueryInput from './components/QueryInput'
import AgentFeed from './components/AgentFeed'
import MemoryPanel from './components/MemoryPanel'
import ReportViewer from './components/ReportViewer'

const API = ''

function Scanlines() {
  return <div className="scanlines" aria-hidden="true" />
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [events, setEvents] = useState([])
  const [report, setReport] = useState('')
  const [memoryCount, setMemoryCount] = useState(0)
  const [memorySources, setMemorySources] = useState([])
  const [error, setError] = useState(null)
  const [activeAgent, setActiveAgent] = useState(null)
  const eventSourceRef = useRef(null)

  const startResearch = useCallback(async (q) => {
    if (!q.trim()) return
    setQuestion(q)
    setError(null)
    setEvents([])
    setReport('')
    setMemoryCount(0)
    setMemorySources([])
    setActiveAgent(null)

    try {
      const res = await fetch(API + '/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok) throw new Error('Failed to start research: ' + res.status)
      const data = await res.json()
      const sid = data.session_id
      setSessionId(sid)
      connectStream(sid)
    } catch (err) {
      if (err.message.includes('fetch')) {
        setError('Cannot connect to backend. Ensure python main.py is running on port 8000.')
      } else {
        setError(err.message)
      }
    }
  }, [])

  const connectStream = useCallback((sid) => {
    if (eventSourceRef.current) eventSourceRef.current.close()
    const es = new EventSource(API + '/stream/' + sid)
    eventSourceRef.current = es

    es.addEventListener('message', (e) => {
      const evt = JSON.parse(e.data)
      setEvents((prev) => [...prev, evt])
      setActiveAgent(evt.agent)

      if (evt.status === 'error') {
        setError(evt.message)
        es.close()
      }
      if (evt.agent === 'system' && evt.status === 'done') {
        setReport(evt.data?.report || '')
        es.close()
      }
      if (evt.agent === 'searcher' && evt.status === 'done') {
        setMemoryCount(evt.data?.count || 0)
      }
    })

    es.onerror = () => { es.close() }

    const memInterval = setInterval(() => {
      fetch(API + '/memory/' + sid)
        .then((r) => r.json())
        .then((d) => {
          setMemoryCount(d.count || 0)
          const sources = (d.findings || []).map((f) => f.metadata?.url || f.metadata?.source_url || '').filter(Boolean)
          setMemorySources([...new Set(sources)])
        })
        .catch(() => {})
    }, 3000)

    const originalClose = es.close.bind(es)
    es.close = () => { clearInterval(memInterval); originalClose() }
  }, [])

  const inProgress = sessionId && !report && !error
  const isComplete = !!report
  const timestamp = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })

  return (
    <div className="min-h-screen bg-bg">
      <Scanlines />
      {inProgress && (
        <div className="stamp stamp--active" aria-hidden="true">
          <div className="stamp__text">ACTIVE</div>
        </div>
      )}

      {/* Header */}
      <header className="terminal-header">
        <div className="terminal-header__inner">
          <div className="terminal-header__brand">
            <div className="terminal-header__dot terminal-header__dot--red" />
            <div className="terminal-header__dot terminal-header__dot--yellow" />
            <div className="terminal-header__dot terminal-header__dot--green" />
            <h1 className="terminal-header__title">
              <span className="terminal-header__icon">{"◎"}</span>
              RESEARCHERMAN
              <span className="terminal-header__sub">intelligence synthesis terminal</span>
            </h1>
          </div>
          <div className="terminal-header__meta">
            {sessionId && (
              <span className="session-id">
                SESSION: <span className="mono">{sessionId}</span>
              </span>
            )}
            <span className="date">{timestamp}</span>
            {inProgress && (
              <span className="pulse-dot">
                <span className="pulse-dot__ring" />
                PROCESSING
              </span>
            )}
            {isComplete && (
              <span className="status-badge status-badge--complete">COMPLETE</span>
            )}
          </div>
        </div>
      </header>

      {/* Main grid */}
      <main className="main-grid">
        <aside className="sidebar">
          <QueryInput onSubmit={startResearch} disabled={inProgress} error={error} />
          <AgentFeed events={events} activeAgent={activeAgent} />
          <MemoryPanel count={memoryCount} sources={memorySources} />
        </aside>

        <section className="report-pane">
          <ReportViewer report={report} />
        </section>
      </main>

      {/* Footer */}
      <footer className="terminal-footer">
        <span>{"◎"} RESEARCHERMAN v0.1.0</span>
        <span>all processing local {"·"} no data leaves this machine</span>
      </footer>
    </div>
  )
}
