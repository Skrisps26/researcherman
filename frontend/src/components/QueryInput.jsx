import { useState } from 'react'

export default function QueryInput({ onSubmit, disabled, error }) {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (value.trim() && !disabled) {
      onSubmit(value)
      setValue('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="query-panel">
      <div className="query-panel__header">
        <span className="query-panel__label">{"▸"} INTAKE</span>
        <span className="query-panel__status">{disabled ? 'LOCKED' : 'READY'}</span>
      </div>

      <form onSubmit={handleSubmit} className="query-panel__form">
        <div className={"query-input-wrap " + (focused ? 'query-input-wrap--focused' : '')}>
          <span className="query-input__prompt">{"❯"}</span>
          <input
            type="text"
            className="query-input"
            placeholder="Enter research question..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            disabled={disabled}
          />
        </div>

        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="query-submit"
        >
          <span className="query-submit__icon">{"▶"}</span>
          INITIATE
        </button>
      </form>

      {error && (
        <div className="error-banner">
          <span className="error-banner__icon">{"⚠"}</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
