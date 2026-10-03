import { useState } from 'react'
import { ArrowsDownUp } from '@phosphor-icons/react'
import StationInput from './StationInput.jsx'

export default function Planner({ from, to, time, busy, compact, onEdit, onFrom, onTo, onTime, onSwap, onNow, onSearch }) {
  const [spin, setSpin] = useState(0)
  const ready = from && to && from.id !== to.id

  // on a phone, once there are results the form folds into one line so the journeys get the screen
  if (compact) {
    return (
      <button type="button" className="summary" onClick={onEdit} aria-label={`Change search: ${from.name} to ${to.name} at ${time}`}>
        <span className="summary-route"><span className="s-name">{from.name}</span><span className="summary-to" aria-hidden="true" /><span className="s-name">{to.name}</span></span>
        <span className="summary-time">{time}</span>
        <span className="summary-edit">Change</span>
      </button>
    )
  }

  return (
    <form className="planner" onSubmit={(e) => { e.preventDefault(); if (ready) onSearch() }}>
      <div className="pair">
        <StationInput label="From" value={from} onChange={onFrom} placeholder="Start station" />
        <button type="button" className="swap" aria-label="Swap origin and destination"
          onClick={() => { setSpin((n) => n + 1); onSwap() }}>
          <ArrowsDownUp size={18} weight="bold" style={{ transform: `rotate(${spin * 180}deg)` }} />
        </button>
        <StationInput label="To" value={to} onChange={onTo} placeholder="Destination station" />
      </div>

      <div className="when">
        <label className="field-label" htmlFor="leave-time">Leave at</label>
        <div className="when-row">
          <input id="leave-time" className="time" type="time" value={time} required
            onChange={(e) => onTime(e.target.value)} />
          <button type="button" className="text-btn" onClick={onNow}>Now</button>
        </div>
      </div>

      <button type="submit" className="primary" disabled={!ready || busy} aria-busy={busy}>
        {busy ? 'Finding journeys…' : 'Find journeys'}
      </button>
      {from && to && from.id === to.id && <p className="hint">Choose two different stations.</p>}
    </form>
  )
}
