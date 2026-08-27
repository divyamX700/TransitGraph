import { useRef } from 'react'

export default function TimePicker({ value, onChange, onNow }) {
  const hhRef = useRef(null)
  const mmRef = useRef(null)

  const [hh, mm] = value ? value.split(':') : ['07', '00']

  function setHour(raw) {
    const v = Math.max(0, Math.min(23, parseInt(raw, 10) || 0))
    onChange(`${String(v).padStart(2, '0')}:${mm}`)
  }

  function setMin(raw) {
    const v = Math.max(0, Math.min(59, parseInt(raw, 10) || 0))
    onChange(`${hh}:${String(v).padStart(2, '0')}`)
  }

  function stepHour(dir) { setHour(parseInt(hh, 10) + dir) }
  function stepMin(dir)  { setMin(parseInt(mm, 10) + dir) }

  function handleHhKey(e) {
    if (e.key === 'ArrowUp')   { e.preventDefault(); stepHour(1) }
    if (e.key === 'ArrowDown') { e.preventDefault(); stepHour(-1) }
  }
  function handleMmKey(e) {
    if (e.key === 'ArrowUp')   { e.preventDefault(); stepMin(1) }
    if (e.key === 'ArrowDown') { e.preventDefault(); stepMin(-1) }
  }

  return (
    <div className="time-seg-wrap">
      {/* Hour segment */}
      <div className="time-seg-group">
        <button type="button" className="time-seg-step" onClick={() => stepHour(1)} tabIndex={-1} aria-label="Hour up">
          <ChevUp />
        </button>
        <input
          ref={hhRef}
          type="number"
          className="time-seg-input"
          value={hh}
          min={0} max={23}
          onChange={e => setHour(e.target.value)}
          onKeyDown={handleHhKey}
          onFocus={e => e.target.select()}
          aria-label="Hour"
        />
        <button type="button" className="time-seg-step" onClick={() => stepHour(-1)} tabIndex={-1} aria-label="Hour down">
          <ChevDown />
        </button>
      </div>

      <span className="time-seg-colon">:</span>

      {/* Minute segment */}
      <div className="time-seg-group">
        <button type="button" className="time-seg-step" onClick={() => stepMin(1)} tabIndex={-1} aria-label="Minute up">
          <ChevUp />
        </button>
        <input
          ref={mmRef}
          type="number"
          className="time-seg-input"
          value={mm}
          min={0} max={59}
          onChange={e => setMin(e.target.value)}
          onKeyDown={handleMmKey}
          onFocus={e => e.target.select()}
          aria-label="Minute"
        />
        <button type="button" className="time-seg-step" onClick={() => stepMin(-1)} tabIndex={-1} aria-label="Minute down">
          <ChevDown />
        </button>
      </div>

      <button type="button" className="time-seg-now" onClick={onNow}>
        NOW
      </button>
    </div>
  )
}

function ChevUp() {
  return (
    <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
      <path d="M1 5L5 1L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function ChevDown() {
  return (
    <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
      <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
