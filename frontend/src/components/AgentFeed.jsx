import { useEffect, useRef } from 'react'

const AGENT_META = {
  planner:  { label: 'PLANNER',  icon: '◈', color: 'blue' },
  searcher: { label: 'SEARCHER', icon: '◎', color: 'amber' },
  critic:   { label: 'CRITIC',   icon: '◆', color: 'red' },
  writer:   { label: 'WRITER',   icon: '✦', color: 'green' },
  system:   { label: 'SYSTEM',   icon: '⚙', color: 'slate' },
}

function StatusLine({ event }) {
  const meta = AGENT_META[event.agent] || AGENT_META.system
  const isDone = event.status === 'done'
  const isWorking = event.status === 'working'
  const isStarted = event.status === 'started'
  const isError = event.status === 'error'

  let cls = 'status-line'
  if (isDone) cls += ' status-line--done'
  if (isWorking) cls += ' status-line--working'
  if (isStarted) cls += ' status-line--started'
  if (isError) cls += ' status-line--error'

  return (
    <div className={cls}>
      <span className="status-line__icon">
        {isDone && '✓'}
        {isWorking && <span className="spinner">◌</span>}
        {isStarted && '▸'}
        {isError && '✕'}
        {!isDone && !isWorking && !isStarted && !isError && '○'}
      </span>
      <span className={'status-line__agent status-line__agent--' + meta.color}>
        {meta.icon} {meta.label}
      </span>
      <span className="status-line__msg">{event.message}</span>
    </div>
  )
}

export default function AgentFeed({ events, activeAgent }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [events])

  return (
    <div className="agent-feed">
      <div className="agent-feed__header">
        <span>{"▸"} ACTIVITY LOG</span>
        <span className="agent-feed__count">
          {events.length > 0 && <span className="mono">{events.length}</span>}
        </span>
      </div>

      <div className="agent-feed__log" ref={scrollRef}>
        {events.length === 0 && (
          <div className="agent-feed__empty">
            <span className="agent-feed__empty-icon">◎</span>
            <span>Awaiting queries...</span>
          </div>
        )}
        {events.map((evt, i) => (
          <StatusLine event={evt} key={evt.agent + '-' + i} />
        ))}
      </div>
    </div>
  )
}
