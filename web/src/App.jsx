import { useState, useEffect, useCallback } from 'react'
import { ArrowsDownUp, MagnifyingGlass } from '@phosphor-icons/react'
import StationInput from './StationInput.jsx'
import RouteCard from './RouteCard.jsx'
import MapView from './MapView.jsx'
import { SkeletonCard } from './components.jsx'
import TimePicker from './TimePicker.jsx'
import { nowMins, formatTime } from './utils.js'

// Format minutes to HH:MM for time input default
function minsToTimeStr(mins) {
  const h = Math.floor(mins / 60) % 24
  const m = mins % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export default function App() {
  const [from, setFrom] = useState(null)
  const [to, setTo] = useState(null)
  const [timeStr, setTimeStr] = useState(minsToTimeStr(nowMins()))
  const [routes, setRoutes] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeIdx, setActiveIdx] = useState(null)
  const [hoveredIdx, setHoveredIdx] = useState(null)
  const [shapesGeoJSON, setShapesGeoJSON] = useState(null)
  const [stationsMap, setStationsMap] = useState(null)

  const API = import.meta.env.VITE_API_URL || ''

  // Load map shapes once
  useEffect(() => {
    fetch(`${API}/api/shapes`)
      .then(r => r.json())
      .then(data => { if (!data.error) setShapesGeoJSON(data) })
      .catch(console.error)
      
    fetch(`${API}/api/stations`)
      .then(r => r.json())
      .then(setStationsMap)
      .catch(console.error)
  }, [])

  function swap() {
    const tmp = from
    setFrom(to)
    setTo(tmp)
    setRoutes(null)
    setActiveIdx(null)
  }

  async function performSearch(overrideTimeStr) {
    if (!from || !to) return
    setLoading(true)
    setError(null)
    setRoutes(null)
    setActiveIdx(null)

    const tStr = overrideTimeStr || timeStr
    const [h, m] = tStr.split(':').map(Number)
    const mins = h * 60 + m

    try {
      const res = await fetch(`${API}/api/route?from=${from.id}&to=${to.id}&time=${mins}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setRoutes(data.routes || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function search(e) {
    if (e) e.preventDefault()
    performSearch()
  }

  function handleNowClick() {
    const nowStr = minsToTimeStr(nowMins())
    setTimeStr(nowStr)
    if (from && to) {
      performSearch(nowStr)
    }
  }

  function handleCardSelect(idx) {
    setActiveIdx(prev => prev === idx ? null : idx)
  }

  const activeRouteLegs = activeIdx !== null && routes ? routes[activeIdx] : null
  const hoveredRouteLegs = hoveredIdx !== null && routes ? routes[hoveredIdx] : null

  const isDataLoaded = shapesGeoJSON && stationsMap

  return (
    <div className="app-shell">
      {/* Nav */}
      <nav className="nav">
        <a href="/" className="nav-logo">
          <span className="nav-logo-dot" />
          TransitGraph
        </a>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Mumbai Suburban Railway
        </span>
      </nav>

      {/* Main split layout */}
      <div className="main-layout">

        {/* Left panel */}
        <div className="panel">
          {!isDataLoaded ? (
            <div style={{ padding: 'var(--space-5)' }}>
              <SkeletonCard />
              <div style={{ height: 20 }} />
              <SkeletonCard />
              <div style={{ height: 20 }} />
              <SkeletonCard />
            </div>
          ) : (
            <>
              <form className="search-form" onSubmit={search}>
            <StationInput
              id="from-input"
              label="From"
              value={from}
              onChange={setFrom}
              placeholder="e.g. Churchgate"
            />
            <StationInput
              id="to-input"
              label="To"
              value={to}
              onChange={setTo}
              placeholder="e.g. Virar"
            />

            <div className="form-actions">
              <button type="button" className="swap-btn" onClick={swap} title="Swap stations">
                <ArrowsDownUp size={16} weight="bold" />
              </button>
              <TimePicker
                value={timeStr}
                onChange={setTimeStr}
                onNow={handleNowClick}
              />
            </div>

            <button
              type="submit"
              className={`search-btn${loading ? ' loading' : ''}`}
              disabled={!from || !to || loading}
            >
              {loading ? 'Finding routes…' : 'Find Routes'}
            </button>
          </form>

          {/* Results */}
          <div className="panel-scroll">
            {error && <div className="error-bar">{error}</div>}

            {loading && (
              <>
                <div className="results-header">Searching…</div>
                <SkeletonCard />
                <SkeletonCard />
              </>
            )}

            {!loading && routes === null && !error && (
              <div className="empty-state">
                <MagnifyingGlass size={40} weight="thin" style={{ opacity: 0.3 }} />
                <p>Enter stations above to find routes</p>
              </div>
            )}

            {!loading && routes?.length === 0 && (
              <div className="empty-state">
                <p>No routes found between these stations</p>
              </div>
            )}

            {!loading && routes && routes.length > 0 && (
              <>
                <div className="results-header">
                  {routes.length} route{routes.length > 1 ? 's' : ''} found
                </div>
                {routes.map((route, i) => (
                  <RouteCard
                    key={i}
                    route={route}
                    index={i}
                    isActive={activeIdx === i}
                    onSelect={handleCardSelect}
                    onHover={setHoveredIdx}
                  />
                ))}
              </>
            )}
          </div>
        </>
          )}
        </div>

        {/* Map */}
        {isDataLoaded ? (
          <MapView
            shapesGeoJSON={shapesGeoJSON}
            activeRouteLegs={activeRouteLegs}
            stationsMap={stationsMap}
          />
        ) : (
          <div className="map-container" style={{ background: '#0C0E13', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ color: 'var(--text-muted)', fontFamily: 'Geist Mono', fontSize: 13 }}>
              Loading network graph...
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
