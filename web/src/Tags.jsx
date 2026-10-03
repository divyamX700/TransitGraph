import { PersonSimpleWalk } from '@phosphor-icons/react'
import { lineInfo, inkOn } from './lines.js'

// How a leg is read: a train is a rectangular tag with sleeper ticks, metro is a round roundel,
// a walk is a dotted outline. Colour names the line; the shape names the mode.
export function LineTag({ id, quiet, letter }) {
  const l = lineInfo(id)
  const style = { '--c': l.color, '--on': inkOn(l.color) }
  const metro = l.mode === 'METRO' || l.mode === 'MONORAIL'
  return (
    <span className={`tag ${metro ? 'tag-metro' : 'tag-train'}${letter ? ' tag-letter' : ''}`} style={style} title={l.name}>
      {!quiet && <span className="sr-only">{metro ? `${l.name}` : `${l.name}, local train`}</span>}
      <span aria-hidden="true">{letter || l.label}</span>
    </span>
  )
}

// The line badges of a station: a metro station has its line, a local station one lettered box per
// railway that calls there (W, C, H...)
export function StationBadges({ station }) {
  if (station.mode !== 'LOCAL') return <LineTag id={station.line} />
  const letters = new Map()
  for (const id of station.lines || []) letters.set(lineInfo(id).letter, id)
  return [...letters].map(([letter, id]) => <LineTag key={id} id={id} letter={letter} />)
}

export function WalkTag({ compact }) {
  return (
    <span className={`tag tag-walk${compact ? ' compact' : ''}`}>
      <PersonSimpleWalk size={16} weight="bold" aria-hidden="true" />
      {compact ? <span className="sr-only">Walk</span> : <span>Walk</span>}
    </span>
  )
}

// A short stroke in the style of a mode, for legends
export function ModeStroke({ mode, color = 'var(--ink)' }) {
  return <span className={`stroke stroke-${mode}`} style={{ '--c': color }} aria-hidden="true" />
}
