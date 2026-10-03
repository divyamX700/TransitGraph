import { useCallback, useEffect, useRef, useState } from 'react'
import Planner from './Planner.jsx'
import Journeys from './Journeys.jsx'
import MapView from './MapView.jsx'
import { fetchLines, fetchShapes, fetchStations, findRoutes } from './api.js'
import { Desktop, Moon, Sun } from '@phosphor-icons/react'
import { applyMode, nextMode, storedMode } from './theme.js'
import { describeJourneys, fromHHMM, nowMinutes, setNetwork, toHHMM } from './lines.js'

const SLOW_MS = 4000

function useNarrow() {
  const query = '(max-width: 859px)'
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const m = window.matchMedia(query)
    const on = () => setNarrow(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return narrow
}

function Wordmark() {
  // the logo is a small route diagram: one line leaves its origin and splits to two destinations
  return (
    <a className="wordmark" href="./" aria-label="TransitGraph, home">
      <svg className="mark" width="34" height="28" viewBox="0 0 34 28" aria-hidden="true">
        <g fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M11 21h6l5-12h5" />
          <path d="M17 21h10" />
          <circle cx="6.5" cy="21" r="3.9" />
        </g>
        <circle cx="30" cy="9" r="3" fill="currentColor" />
        <circle cx="30" cy="21" r="3" fill="currentColor" />
      </svg>
      <span>TransitGraph</span>
    </a>
  )
}

// Placeholder tickets while the network or a search is loading
function Skeleton({ label, note }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {note && <p className="skeleton-note">{note}</p>}
      {[0, 1].map((n) => (
        <div className="skel-ticket" key={n} aria-hidden="true">
          <span className="skel skel-band" />
          <span className="skel skel-times" />
          <span className="skel skel-strip" />
        </div>
      ))}
    </div>
  )
}

const THEME_ICON = { system: Desktop, light: Sun, dark: Moon }

function ThemeToggle() {
  const [mode, setMode] = useState(storedMode)
  const Icon = THEME_ICON[mode]
  const next = nextMode(mode)
  return (
    <button type="button" className="theme-btn" aria-label={`Theme: ${mode}. Switch to ${next}`} title={`Theme: ${mode}`}
      onClick={() => { applyMode(next); setMode(next) }}>
      <Icon size={20} weight="bold" />
      <span>{mode === 'system' ? 'Auto' : mode === 'light' ? 'Light' : 'Dark'}</span>
    </button>
  )
}

export default function App() {
  const [stations, setStations] = useState(null)
  const [lines, setLines] = useState(null)
  const [shapes, setShapes] = useState(null)
  const [loadError, setLoadError] = useState(null)

  const [from, setFrom] = useState(null)
  const [to, setTo] = useState(null)
  const [time, setTime] = useState(toHHMM(nowMinutes()))
  const [state, setState] = useState({ phase: 'idle' }) // idle | loading | slow | done | error
  const [found, setFound] = useState({ shown: [], slower: [] })
  const [showSlower, setShowSlower] = useState(false)
  const [selected, setSelected] = useState(0)   // the journey drawn on the map
  const [expanded, setExpanded] = useState(-1)   // the journey whose steps are open
  const [queryMinutes, setQueryMinutes] = useState(0)
  const narrow = useNarrow()
  const [editing, setEditing] = useState(true)
  const resultsRef = useRef(null)
  const request = useRef(null)

  // network data: stations and lines first (small), shapes after (large, only the map needs them)
  useEffect(() => {
    let alive = true
    Promise.all([fetchStations(), fetchLines()])
      .then(([st, ln]) => {
        if (!alive) return
        setNetwork(ln, st)
        setStations(st)
        setLines(ln)
      })
      .catch((e) => alive && setLoadError(e.message))
    fetchShapes().then((s) => alive && setShapes(s)).catch(() => {})
    return () => { alive = false }
  }, [])

  const search = useCallback(async (f, t, clock) => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    const minutes = fromHHMM(clock)
    setState({ phase: 'loading' })
    const slow = setTimeout(() => setState((s) => (s.phase === 'loading' ? { phase: 'slow' } : s)), SLOW_MS)
    try {
      const data = await findRoutes(f.id, t.id, minutes, controller.signal)
      setFound(describeJourneys(data.routes || []))
      setShowSlower(false)
      setSelected(0)
      setExpanded(-1)
      setQueryMinutes(minutes)
      setState({ phase: 'done' })
      setEditing(false)
      history.replaceState(null, '', `?from=${f.id}&to=${t.id}&at=${clock}`)
      resultsRef.current?.focus({ preventScroll: false })
    } catch (e) {
      if (e.name !== 'AbortError') setState({ phase: 'error', message: e.message })
    } finally {
      clearTimeout(slow)
    }
  }, [])

  // a shared link opens with its search already run
  useEffect(() => {
    if (!stations) return
    const q = new URLSearchParams(location.search)
    const f = stations[q.get('from')]
    const t = stations[q.get('to')]
    const at = /^\d\d:\d\d$/.test(q.get('at') || '') ? q.get('at') : null
    if (f && t) {
      const a = { id: q.get('from'), ...f }
      const b = { id: q.get('to'), ...t }
      setFrom(a)
      setTo(b)
      if (at) setTime(at)
      search(a, b, at || time)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stations])

  // any change to the search drops the old results, and an answer still on its way
  const clearResults = () => {
    request.current?.abort()
    setFound({ shown: [], slower: [] })
    setState({ phase: 'idle' })
  }
  const swap = () => {
    setFrom(to)
    setTo(from)
    clearResults()
  }

  const items = showSlower ? [...found.shown, ...found.slower] : found.shown
  const legs = state.phase === 'done' && items[selected] ? items[selected].legs : null

  return (
    <div className="shell">
      <header className="bar">
        <Wordmark />
        <p className="bar-note">Mumbai local trains and metro</p>
        <ThemeToggle />
      </header>

      <main className="layout">
        <section className="rail" aria-label="Journey planner">
          <Planner
            from={from} to={to} time={time} busy={state.phase === 'loading' || state.phase === 'slow'}
            compact={narrow && !editing && state.phase === 'done'} onEdit={() => setEditing(true)}
            onFrom={(s) => { setFrom(s); clearResults() }}
            onTo={(s) => { setTo(s); clearResults() }}
            onTime={setTime}
            onNow={() => setTime(toHHMM(nowMinutes()))}
            onSwap={swap}
            onSearch={() => search(from, to, time)}
          />

          <div className="results" ref={resultsRef} tabIndex={-1} aria-live="polite">
            {loadError && <p className="notice error" role="alert">{loadError}. Reload to try again.</p>}
            {!stations && !loadError && <Skeleton label="Loading stations" />}

            {state.phase === 'idle' && stations && (
              <p className="empty">Pick a start and a destination.</p>
            )}
            {(state.phase === 'loading' || state.phase === 'slow') && (
              <Skeleton label={state.phase === 'slow' ? 'The server is waking up. The first search can take a minute.' : 'Finding journeys'}
                note={state.phase === 'slow' ? 'The server is waking up. The first search can take a minute.' : null} />
            )}
            {state.phase === 'error' && (
              <p className="notice error" role="alert">
                {state.message}. <button type="button" className="text-btn" onClick={() => search(from, to, time)}>Try again</button>
              </p>
            )}
            {state.phase === 'done' && items.length === 0 && (
              <div className="empty">
                <p className="empty-title">No journey found</p>
                <p>Nothing runs from {from.name} to {to.name} after {time}. Try an earlier time.</p>
              </div>
            )}
            {state.phase === 'done' && items.length > 0 && (
              <>
                <h2 className="results-title">{items.length === 1 ? '1 journey' : `${items.length} journeys`}<span className="soft"> · {from.name} to {to.name}</span></h2>
                <Journeys items={items} selected={selected} expanded={expanded} queryMinutes={queryMinutes}
                  onSelect={(i) => { setExpanded(i === expanded ? -1 : i); setSelected(i) }} />
                {found.slower.length > 0 && !showSlower && (
                  <p className="more">
                    <button type="button" className="text-btn" onClick={() => setShowSlower(true)}>
                      Show {found.slower.length} later {found.slower.length === 1 ? 'journey' : 'journeys'} with fewer changes
                    </button>
                  </p>
                )}
              </>
            )}
          </div>

        </section>

        <section className="mapbox" aria-label="Map">
          <MapView shapes={shapes} legs={legs} lines={lines} />
        </section>
      </main>
    </div>
  )
}
