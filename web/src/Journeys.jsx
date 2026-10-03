import { CaretDown, MapPin } from '@phosphor-icons/react'
import { LineTag, WalkTag } from './Tags.jsx'
import { buildSteps, clock, duration, isNextDay, lineInfo, metres, modeName, station, towards } from './lines.js'

function Clock({ min }) {
  return (
    <span className="clock">
      {clock(min)}
      {isNextDay(min) && <sup className="plus" title="Next day">+1</sup>}
    </span>
  )
}

function Place({ id }) {
  const s = station(id)
  return (
    <span className="place">
      <span className="place-name">{s.name}</span>
    </span>
  )
}

const legMinutes = (leg) => leg.arr_min - leg.dep_min
const modeOf = (leg) => (leg.is_walk ? 'WALK' : leg.mode)
const colorOf = (leg) => (leg.is_walk ? 'var(--ink-2)' : lineInfo(leg.line).color)

function summary(item) {
  if (item.legs.every((l) => l.is_walk)) return `Walk only · ${metres(item.walkMeters)}`
  const parts = [item.changes === 0 ? 'Direct' :`${item.changes} change${item.changes > 1 ? 's' : ''}`]
  if (item.walkMeters) parts.push(`${metres(item.walkMeters)} walk`)
  return parts.join(' · ')
}

function stripLabel(legs) {
  return legs.map((l) => (l.is_walk ? `walk ${legMinutes(l)} minutes` : `${lineInfo(l.line).name} ${legMinutes(l)} minutes`)).join(', ')
}

// The journey as a code strip: one painted segment per leg, as long as the leg takes
function Strip({ legs }) {
  return (
    <span className="strip" role="img" aria-label={stripLabel(legs)}>
      {legs.map((leg, i) => {
        const minutes = legMinutes(leg)
        return (
          <span key={i} className={`seg seg-${modeOf(leg)}`}
            style={{ flexGrow: Math.max(minutes, 6), '--c': colorOf(leg), '--i': i }}>
            <span className="seg-tag">{leg.is_walk ? <WalkTag compact /> : <LineTag id={leg.line} />}</span>
            <span className="seg-bar" />
            <span className="seg-min">{minutes}<span className="unit"> min</span></span>
          </span>
        )
      })}
    </span>
  )
}

// The journey stop by stop: times on the left, the line down the middle, what to do on the right
function Steps({ legs, queryMinutes }) {
  const steps = buildSteps(legs, queryMinutes)
  return (
    <ol className="route" aria-label="Journey step by step">
      {steps.map((s, i) => (s.type === 'leg' ? <LegRow key={i} leg={s.leg} /> : <StopRow key={i} s={s} />))}
    </ol>
  )
}

function StopRow({ s }) {
  let note = null
  if (s.first && s.wait >= 2) note = `Wait ${duration(s.wait)}`
  else if (!s.first && !s.last && s.wait >= 1) note = `${s.change ? 'Change here, wait' : 'Wait'} ${duration(s.wait)}`
  else if (s.change) note = 'Change here'
  return (
    <li className={`row stop${s.first ? ' first' : ''}${s.last ? ' last' : ''}`}>
      <span className="r-time">
        {s.first ? <Clock min={s.dep} /> : <Clock min={s.arr} />}
        {!s.first && s.dep != null && s.dep - s.arr >= 1 && <span className="r-dep"><Clock min={s.dep} /></span>}
      </span>
      <span className="rail" aria-hidden="true">
        {s.up && <i className={`rl up ${modeOf(s.up)}`} style={{ '--c': colorOf(s.up) }} />}
        {s.down && <i className={`rl dn ${modeOf(s.down)}`} style={{ '--c': colorOf(s.down) }} />}
        <b className="node" />
      </span>
      <div className="r-body">
        <p className="r-name"><Place id={s.id} /></p>
        {note && <p className="r-note">{note}</p>}
      </div>
    </li>
  )
}

function LegRow({ leg }) {
  const heading = towards(leg)
  return (
    <li className="row leg">
      <span className="r-time" />
      <span className="rail" aria-hidden="true"><i className={`rl full ${modeOf(leg)}`} style={{ '--c': colorOf(leg) }} /></span>
      <div className="r-body">
        {leg.is_walk ? (
          <>
            <WalkTag />
            <span className="r-what">{leg.walk_m >= 30 ? `${metres(leg.walk_m)} · ` : ''}{legMinutes(leg)} min</span>
          </>
        ) : (
          <>
            <LineTag id={leg.line} />
            <span className="r-what">{modeName(leg.mode)}{heading ? ` towards ${heading}` : ''} · {legMinutes(leg)} min</span>
          </>
        )}
      </div>
    </li>
  )
}

export default function Journeys({ items, selected, expanded, onSelect, queryMinutes }) {
  return (
    <ul className="journeys">
      {items.map((item, i) => {
        const open = expanded === i
        const on = selected === i
        const labels = item.labels
        return (
          <li key={`${item.depart}-${item.arrive}-${item.changes}`} className={`journey${on ? ' on' : ''}${open ? ' open' : ''}`}>
            <button type="button" className="journey-head" aria-expanded={open} onClick={() => onSelect(i)}>
              <span className="band">
                <span>{labels.length ? labels.join(' · ') : `${item.changes} change${item.changes === 1 ? '' : 's'}`}</span>
                {on && <span className="onmap"><MapPin size={15} weight="fill" aria-hidden="true" />On the map</span>}
              </span>
              <span className="journey-main">
                <span className="journey-times">
                  <Clock min={item.depart} />
                  <span className="to" aria-hidden="true" />
                  <Clock min={item.arrive} />
                  <span className="journey-dur">{duration(item.arrive - item.depart)}</span>
                </span>
                <Strip legs={item.legs} />
              </span>
              <span className="stub">
                <span>{summary(item)}</span>
                <span className="journey-steps">{open ? 'Hide steps' : 'Steps'}<CaretDown size={14} weight="bold" aria-hidden="true" /></span>
              </span>
            </button>
            {open && <Steps legs={item.legs} queryMinutes={queryMinutes} />}
          </li>
        )
      })}
    </ul>
  )
}
