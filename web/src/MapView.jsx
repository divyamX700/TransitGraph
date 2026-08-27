import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import { useEffect, useState, useMemo } from 'react'
import L from 'leaflet'
import { getLineColor } from './utils.js'

const DARK_TILES = `https://basemaps.cartocdn.com/rastertiles/dark_matter/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`
const TILES_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

// Haversine distance squared (fast comparison, no sqrt needed)
function dist2(lat1, lon1, lat2, lon2) {
  const dlat = lat1 - lat2, dlon = lon1 - lon2
  return dlat * dlat + dlon * dlon
}

// Find index of closest coordinate [lon, lat] to target [lat, lon]
function closestIdx(coords, lat, lon) {
  let best = 0, bestD = Infinity
  for (let i = 0; i < coords.length; i++) {
    const d = dist2(coords[i][1], coords[i][0], lat, lon)
    if (d < bestD) { bestD = d; best = i }
  }
  return best
}

// Slice shape coords array between two station coordinates
function sliceShape(coords, fromLat, fromLon, toLat, toLon) {
  const i = closestIdx(coords, fromLat, fromLon)
  const j = closestIdx(coords, toLat,   toLon)
  const [a, b] = i <= j ? [i, j] : [j, i]
  return coords.slice(a, b + 1).map(([lon, lat]) => [lat, lon])
}

function BoundsFitter({ slices }) {
  const map = useMap()
  useEffect(() => {
    if (!slices || slices.length === 0) return
    const all = slices.flatMap(s => s.positions)
    if (all.length > 0) map.flyToBounds(all, { padding: [60, 60], duration: 0.8 })
  }, [slices, map])
  return null
}

// Split-circle DivIcon for interchange stations
function makeInterchangeIcon(colorA, colorB, size = 18) {
  const r = size / 2
  const svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
    <clipPath id="lhalf"><rect x="0" y="0" width="${r}" height="${size}"/></clipPath>
    <clipPath id="rhalf"><rect x="${r}" y="0" width="${r}" height="${size}"/></clipPath>
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="${colorA}" clip-path="url(#lhalf)"/>
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="${colorB}" clip-path="url(#rhalf)"/>
    <circle cx="${r}" cy="${r}" r="${r - 1}" fill="none" stroke="#fff" stroke-width="2"/>
  </svg>`
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [size, size],
    iconAnchor: [r, r]
  })
}

export default function MapView({ shapesGeoJSON, activeRouteLegs, stationsMap }) {
  const center = [19.076, 72.877]

  // Index shape_id → feature (direct O(1) lookup)
  const shapeByShapeId = useMemo(() => {
    if (!shapesGeoJSON) return {}
    const idx = {}
    for (const f of shapesGeoJSON.features) {
      const sid = f.properties?.shape_id
      if (sid) idx[sid] = f
    }
    return idx
  }, [shapesGeoJSON])

  const [activeSlices, setActiveSlices] = useState([])

  useEffect(() => {
    if (!activeRouteLegs || !stationsMap || Object.keys(shapeByShapeId).length === 0) {
      setActiveSlices([])
      return
    }

    const slices = []
    for (const leg of activeRouteLegs) {
      const fromSt = stationsMap[leg.from]
      const toSt   = stationsMap[leg.to]
      if (!fromSt || !toSt) continue

      // leg.route_id IS the shape_id from RAPTOR
      const feature = shapeByShapeId[leg.route_id]
      if (!feature) {
        console.warn('Shape not found:', leg.route_id)
        continue
      }

      const coords = feature.geometry?.coordinates
      if (!coords || coords.length < 2) continue

      const positions = sliceShape(coords, fromSt.lat, fromSt.lon, toSt.lat, toSt.lon)

      if (positions.length >= 2) {
        const rid   = feature.properties.route_id || ''
        const color = getLineColor(rid)
        slices.push({ positions, color })
      }
    }
    setActiveSlices(slices)
  }, [activeRouteLegs, stationsMap, shapeByShapeId])

  const hasActive = !!activeRouteLegs

  // Compute station dots
  const stationDots = useMemo(() => {
    if (!hasActive || !activeRouteLegs || !stationsMap) return null
    const legs = activeRouteLegs

    const srcLeg  = legs[0]
    const dstLeg  = legs[legs.length - 1]
    const srcSt   = stationsMap[srcLeg.from]
    const dstSt   = stationsMap[dstLeg.to]
    const srcColor = getLineColor(shapeByShapeId[srcLeg.route_id]?.properties?.route_id || '')
    const dstColor = getLineColor(shapeByShapeId[dstLeg.route_id]?.properties?.route_id || '')

    const interchanges = legs.slice(0, -1).map((leg, i) => {
      const st      = stationsMap[leg.to]
      const colorA  = getLineColor(shapeByShapeId[leg.route_id]?.properties?.route_id || '')
      const colorB  = getLineColor(shapeByShapeId[legs[i + 1].route_id]?.properties?.route_id || '')
      return { st, colorA, colorB, name: leg.to }
    })

    return { srcSt, dstSt, srcColor, dstColor, interchanges,
             srcName: srcLeg.from, dstName: dstLeg.to }
  }, [hasActive, activeRouteLegs, stationsMap, shapeByShapeId])

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={11}
        style={{ width: '100%', height: '100%' }}
        zoomControl={false}
      >
        <TileLayer url={DARK_TILES} attribution={TILES_ATTR} />

        {/* Background lines — only shown when no active route */}
        {!hasActive && shapesGeoJSON?.features?.map((feature, i) => {
          if (!feature.geometry?.coordinates) return null
          const color     = getLineColor(feature.properties?.route_id || '')
          const positions = feature.geometry.coordinates.map(([lon, lat]) => [lat, lon])
          return (
            <Polyline key={`bg-${i}`} positions={positions}
              pathOptions={{ color, weight: 2, opacity: 0.5 }} />
          )
        })}

        {/* Active sliced legs */}
        {activeSlices.map((slice, i) => (
          <Polyline key={`active-${i}`} positions={slice.positions}
            pathOptions={{ color: slice.color, weight: 5, opacity: 1 }} />
        ))}

        {/* Station dots */}
        {stationDots && (<>
          {/* Source */}
          {stationDots.srcSt && (
            <CircleMarker center={[stationDots.srcSt.lat, stationDots.srcSt.lon]}
              pathOptions={{ color: '#fff', fillColor: stationDots.srcColor, fillOpacity: 1, weight: 2.5 }}
              radius={7}>
              <Tooltip direction="top" offset={[0, -8]}>{stationDots.srcName.replace(/_/g, ' ')}</Tooltip>
            </CircleMarker>
          )}

          {/* Interchanges — split DivIcon (rendered via useEffect with Leaflet.Marker) */}
          {stationDots.interchanges.map((xfr, i) => xfr.st && (
            <SplitMarker key={`xfr-${i}`}
              lat={xfr.st.lat} lon={xfr.st.lon}
              colorA={xfr.colorA} colorB={xfr.colorB}
              name={xfr.name} />
          ))}

          {/* Destination */}
          {stationDots.dstSt && (
            <CircleMarker center={[stationDots.dstSt.lat, stationDots.dstSt.lon]}
              pathOptions={{ color: '#fff', fillColor: stationDots.dstColor, fillOpacity: 1, weight: 2.5 }}
              radius={7}>
              <Tooltip direction="top" offset={[0, -8]}>{stationDots.dstName.replace(/_/g, ' ')}</Tooltip>
            </CircleMarker>
          )}
        </>)}

        <BoundsFitter slices={activeSlices} />
      </MapContainer>
    </div>
  )
}

// Interchange split-circle using Leaflet DivIcon + react-leaflet Marker
import { Marker } from 'react-leaflet'

function SplitMarker({ lat, lon, colorA, colorB, name }) {
  const icon = useMemo(() => makeInterchangeIcon(colorA, colorB), [colorA, colorB])
  return (
    <Marker position={[lat, lon]} icon={icon}>
      <Tooltip direction="top" offset={[0, -10]}>{name.replace(/_/g, ' ')}</Tooltip>
    </Marker>
  )
}
