import { Fragment, useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap, ZoomControl } from 'react-leaflet'
import { lineInfo, station } from './lines.js'
import { ModeStroke, LineTag } from './Tags.jsx'
import { useDark } from './theme.js'

const KEY = import.meta.env.VITE_CARTO_API_KEY

// follows a media query live (dark mode, phone width)
function useMedia(query) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const m = window.matchMedia(query)
    const on = () => setMatches(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [query])
  return matches
}
// With the project's CARTO key: CARTO basemaps (muted light and dark greys, so the transit lines are what stands out). Without one (local
// development) CARTO refuses tiles, so plain OpenStreetMap tiles are used and darkened with CSS.
const TILES = {
  light: KEY ? `https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${KEY}` : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  dark: KEY ? `https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${KEY}` : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
}
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

const toLatLng = ([lon, lat]) => [lat, lon]

// index of the vertex nearest to a point, searching from `start`
function nearest(coords, point, start = 0) {
  let best = start
  let bestD = Infinity
  for (let i = start; i < coords.length; i++) {
    const dlat = coords[i][1] - point.lat
    const dlon = coords[i][0] - point.lon
    const d = dlat * dlat + dlon * dlon
    if (d < bestD) { bestD = d; best = i }
  }
  return best
}

// the part of a shape between two stations, in travel order
function slice(coords, from, to) {
  const i = nearest(coords, from)
  let j = nearest(coords, to, i)
  if (j <= i) { // shape runs the other way (should not happen): fall back to the plain nearest points
    const a = nearest(coords, from)
    const b = nearest(coords, to)
    return coords.slice(Math.min(a, b), Math.max(a, b) + 1).map(toLatLng)
  }
  return coords.slice(i, j + 1).map(toLatLng)
}

// Many trains share a track; draw each stretch of every line once
function networkLines(shapes) {
  if (!shapes) return []
  const seen = new Set()
  const key = ([lon, lat]) => `${lon.toFixed(3)},${lat.toFixed(3)}`
  return [...shapes.features]
    .sort((a, b) => b.geometry.coordinates.length - a.geometry.coordinates.length)
    .filter((f) => {
      const keys = f.geometry.coordinates.map(key)
      const fresh = keys.filter((k) => !seen.has(k)).length
      if (fresh < keys.length * 0.12) return false
      keys.forEach((k) => seen.add(k))
      return true
    })
    .map((f) => ({ line: f.properties.route_id, positions: f.geometry.coordinates.map(toLatLng) }))
}

function Fit({ positions, bottom, home }) {
  const map = useMap()
  useEffect(() => {
    if (positions?.length) {
      map.flyToBounds(positions, { paddingTopLeft: [48, 56], paddingBottomRight: [48, bottom], duration: 0.7, maxZoom: 17 })
    } else {
      map.flyTo([19.1, 72.95], home, { duration: 0.7 }) // back to the whole network
    }
  }, [positions, bottom, home, map])
  return null
}

// A leg drawn the way its mode reads: train = line with sleeper ticks, metro = heavy line in a white
// casing, walk = dotted
function LegStroke({ leg, positions, dark }) {
  if (leg.is_walk) {
    // a row of dots with a halo in the opposite colour, so it reads on any map
    return (
      <>
        <Polyline positions={positions} pathOptions={{ color: dark ? '#0C1A26' : '#fff', weight: 11, dashArray: '0.1 11', lineCap: 'round', opacity: 1 }} />
        <Polyline positions={positions} pathOptions={{ color: dark ? '#fff' : '#0C1A26', weight: 6, dashArray: '0.1 11', lineCap: 'round', opacity: 1 }} />
      </>
    )
  }
  const info = lineInfo(leg.line)
  if (info.mode === 'LOCAL') {
    return (
      <>
        <Polyline positions={positions} pathOptions={{ color: dark ? '#fff' : '#0C1A26', weight: 9, opacity: 0.9, lineCap: 'butt' }} />
        <Polyline positions={positions} pathOptions={{ color: info.color, weight: 6, opacity: 1, lineCap: 'butt' }} />
        <Polyline positions={positions} pathOptions={{ color: '#fff', weight: 6, opacity: 0.9, dashArray: '1.6 9', lineCap: 'butt' }} />
      </>
    )
  }
  return (
    <>
      <Polyline positions={positions} pathOptions={{ color: '#fff', weight: 13, opacity: 1, lineCap: 'round' }} />
      <Polyline positions={positions} pathOptions={{ color: '#0C1A26', weight: 10, opacity: 0.9, lineCap: 'round' }} />
      <Polyline positions={positions} pathOptions={{ color: info.color, weight: 7, opacity: 1, lineCap: 'round' }} />
    </>
  )
}

export default function MapView({ shapes, legs, lines }) {
  const dark = useDark()
  const narrow = useMedia('(max-width: 859px)')
  const network = useMemo(() => networkLines(shapes), [shapes])
  const byShape = useMemo(() => Object.fromEntries((shapes?.features || []).map((f) => [f.properties.shape_id, f])), [shapes])

  const drawn = useMemo(() => {
    if (!legs) return null
    return legs.map((leg) => {
      const a = station(leg.from)
      const b = station(leg.to)
      if (leg.is_walk || !byShape[leg.route_id]) return { leg, positions: [[a.lat, a.lon], [b.lat, b.lon]] }
      // the shape runs near the stations, not through them: join it so the line meets its markers
      return { leg, positions: [[a.lat, a.lon], ...slice(byShape[leg.route_id].geometry.coordinates, a, b), [b.lat, b.lon]] }
    })
  }, [legs, byShape])

  const bounds = useMemo(() => drawn?.flatMap((d) => d.positions), [drawn])

  // the places worth naming: where the journey starts, ends and changes
  const stops = useMemo(() => {
    if (!legs) return []
    const list = [{ id: legs[0].from, kind: 'origin' }]
    legs.slice(0, -1).forEach((l, i) => {
      const next = legs[i + 1].from
      list.push({ id: l.to, kind: 'change' })
      // changing between two stations (local Grant Road, metro Grant Road): mark both ends
      if (next !== l.to) list.push({ id: next, kind: 'change' })
    })
    list.push({ id: legs[legs.length - 1].to, kind: 'dest' })
    return list
  }, [legs])

  // station markers: a ring in the ink colour of the theme, solid at the destination, hollow elsewhere
  const ink = dark ? '#fff' : '#0C1A26'
  const paper = dark ? '#0C1A26' : '#fff'
  const focus = Boolean(legs)

  return (
    <div className={`map-wrap${!KEY && dark ? ' tint-dark' : ''}`}>
      <MapContainer center={[19.1, 72.95]} zoom={narrow ? 10 : 11} minZoom={9} zoomControl={false} preferCanvas className="map" attributionControl>
        <TileLayer key={dark ? 'd' : 'l'} url={dark ? TILES.dark : TILES.light} attribution={ATTRIBUTION} />
        <ZoomControl position="bottomright" />

        {[...network].sort((a, b) => (lineInfo(a.line).mode === 'LOCAL' ? -1 : 1) - (lineInfo(b.line).mode === 'LOCAL' ? -1 : 1)).map((n, i) => {
          const info = lineInfo(n.line)
          const fade = focus ? 0.07 : 1
          // trains have sleeper ticks, metro is a plain solid line
          return info.mode === 'LOCAL' ? (
            <Fragment key={i}>
              <Polyline positions={n.positions} interactive={false} pathOptions={{ color: info.color, weight: 4, opacity: 0.9 * fade, lineCap: 'butt' }} />
              <Polyline positions={n.positions} interactive={false} pathOptions={{ color: '#fff', weight: 4, opacity: 0.85 * fade, dashArray: '1.4 6', lineCap: 'butt' }} />
            </Fragment>
          ) : (
            <Polyline key={i} positions={n.positions} interactive={false} pathOptions={{ color: info.color, weight: 4, opacity: focus ? 0.08 : 0.92, lineCap: 'round' }} />
          )
        })}

        {/* keyed by the leg itself: Leaflet keeps old style options (a walk's dots) on a reused line */}
        {drawn?.map((d, i) => <LegStroke key={`${i}-${d.leg.from}-${d.leg.to}-${d.leg.dep_min}`} leg={d.leg} positions={d.positions} dark={dark} />)}

        {drawn?.filter((d) => d.leg.is_walk && d.leg.walk_m >= 30).map((d, i) => {
          const [a, b] = [d.positions[0], d.positions[d.positions.length - 1]]
          return (
            <CircleMarker key={`w${i}`} center={[(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]} radius={1} pathOptions={{ opacity: 0, fillOpacity: 0 }} interactive={false}>
              <Tooltip permanent direction="left" offset={[-8, 0]} className="map-label map-label-walk">
                Walk {d.leg.arr_min - d.leg.dep_min} min
              </Tooltip>
            </CircleMarker>
          )
        })}

        {stops.map((s, i) => {
          const st = station(s.id)
          if (st.lat == null) return null
          // on a phone only the ends are named, so labels do not pile up
          const named = s.kind !== 'change' || !narrow
          return (
            <CircleMarker key={i} center={[st.lat, st.lon]} radius={s.kind === 'change' ? 6 : 8}
              pathOptions={{ color: ink, weight: 3, fillColor: s.kind === 'dest' ? ink : paper, fillOpacity: 1 }}>
              {named && (
                <Tooltip permanent direction={s.kind === 'dest' ? 'bottom' : s.kind === 'change' ? 'right' : 'top'}
                  offset={s.kind === 'change' ? [8, 0] : [0, s.kind === 'dest' ? 8 : -8]} className={`map-label map-label-${s.kind}`}>
                  {st.name}
                </Tooltip>
              )}
            </CircleMarker>
          )
        })}

        <Fit positions={bounds} bottom={narrow ? 76 : 88} home={narrow ? 10 : 11} />
      </MapContainer>
      <Legend lines={lines} />
    </div>
  )
}

function Legend({ lines }) {
  const groups = [
    ['Local trains', Object.keys(lines || {}).filter((id) => lines[id].mode === 'LOCAL' && id !== 'WR_DAHANU')],
    ['Metro', Object.keys(lines || {}).filter((id) => lines[id].mode !== 'LOCAL')],
  ]
  return (
    <details className="legend">
      <summary>
        <span className="legend-keys">
          <span><ModeStroke mode="LOCAL" /> Local train</span>
          <span><ModeStroke mode="METRO" /> Metro</span>
          <span><ModeStroke mode="WALK" /> Walk</span>
        </span>
        <span className="legend-more">Lines</span>
      </summary>
      {groups.map(([title, ids]) => (
        <div className="legend-group" key={title}>
          <h3>{title}</h3>
          <ul>
            {ids.map((id) => (
              <li key={id}><LineTag id={id} quiet /><span>{lineInfo(id).name.replace(/^Metro /, '')}</span></li>
            ))}
          </ul>
        </div>
      ))}
    </details>
  )
}
