// Line color map — matches CSS design tokens
export const LINE_COLORS = {
  WR_MAIN:    '#2563EB', // Western
  WR_DAHANU:  '#2563EB', // Dahanu (same corridor)
  CR_MAIN:    '#DC2626', // Central
  CR_HARBOUR: '#0891B2', // Harbour
  CR_TRANS:   '#7C3AED', // Trans-Harbour
  CR_PORT:    '#059669', // Port / Uran
}

export const LINE_NAMES = {
  WR_MAIN:    'Western',
  WR_DAHANU:  'Western',
  CR_MAIN:    'Central',
  CR_HARBOUR: 'Harbour',
  CR_TRANS:   'Trans-Harbour',
  CR_PORT:    'Port',
}

export const LINE_CSS_CLASS = {
  WR_MAIN:    'line-western',
  WR_DAHANU:  'line-dahanu',
  CR_MAIN:    'line-central',
  CR_HARBOUR: 'line-harbour',
  CR_TRANS:   'line-trans',
  CR_PORT:    'line-port',
}

// Extract the route family from a shape_id like "SHP_WR_MAIN_..."
export function routeIdFromShapeId(shapeId) {
  // shape_id format: SHP_WR_MAIN_CSMT_TO_VIRAR_xxxx
  const parts = shapeId.split('_')
  if (parts.length >= 3) {
    return `${parts[1]}_${parts[2]}`
  }
  return null
}

// Get color for a route_id string (handles canonical route_id OR full shape_id)
export function getLineColor(routeId) {
  if (!routeId) return '#4A5068'
  const u = routeId.toUpperCase()
  // Order matters: check most-specific first
  if (u.includes('WR_DAHANU') || u.includes('DAHANU')) return LINE_COLORS.WR_DAHANU
  if (u.includes('WR_MAIN')   || u.includes('_WR_'))   return LINE_COLORS.WR_MAIN
  if (u.includes('CR_HARBOUR')|| u.includes('HARBOUR')) return LINE_COLORS.CR_HARBOUR
  if (u.includes('CR_TRANS')  || u.includes('TRANS'))   return LINE_COLORS.CR_TRANS
  if (u.includes('CR_PORT')   || u.includes('URAN'))    return LINE_COLORS.CR_PORT
  if (u.includes('CR_MAIN')   || u.includes('_CR_'))    return LINE_COLORS.CR_MAIN
  return '#4A5068'
}

export function getLineName(routeId) {
  if (!routeId) return ''
  const u = routeId.toUpperCase()
  if (u.includes('WR_DAHANU') || u.includes('DAHANU')) return 'Dahanu'
  if (u.includes('WR_MAIN')   || u.includes('_WR_'))   return 'Western'
  if (u.includes('CR_HARBOUR')|| u.includes('HARBOUR')) return 'Harbour'
  if (u.includes('CR_TRANS')  || u.includes('TRANS'))   return 'Trans-Harbour'
  if (u.includes('CR_PORT')   || u.includes('URAN'))    return 'Port'
  if (u.includes('CR_MAIN')   || u.includes('_CR_'))    return 'Central'
  return ''
}

// Format minutes since midnight to HH:MM string
export function formatTime(minsOrString) {
  if (typeof minsOrString === 'string') return minsOrString
  const h = Math.floor(minsOrString / 60) % 24
  const m = minsOrString % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// Current time as minutes since midnight
export function nowMins() {
  const d = new Date()
  return d.getHours() * 60 + d.getMinutes()
}

// HH:MM string to minutes since midnight
export function timeMins(str) {
  const [h, m] = str.split(':').map(Number)
  return h * 60 + m
}

// Duration between two HH:MM strings in "Xh Ym" format
export function duration(dep, arr) {
  let d = timeMins(arr) - timeMins(dep)
  if (d < 0) d += 24 * 60
  const h = Math.floor(d / 60)
  const m = d % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}
