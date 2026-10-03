// Lines, modes and time formatting shared by the planner, journey list and map.

let lines = {}   // line id -> { name, short_name, color, mode }
let stations = {} // stop id -> { name, lat, lon, mode, line }

export function setNetwork(linesMap, stationsMap) {
  lines = linesMap || {}
  stations = stationsMap || {}
}

const LOCAL_LABEL = { WR_DAHANU: 'Western' }

export function lineInfo(id) {
  const l = lines[id]
  if (!l) return { id, name: id, label: id, color: '#5E6E7B', mode: 'LOCAL' }
  const label = l.mode === 'LOCAL'
    ? (LOCAL_LABEL[id] || l.name.replace(/ Line$/, ''))
    : l.short_name
  return { id, ...l, label, letter: LOCAL_LETTER[id] || label[0] }
}

// one letter per railway, for small badges ("Trans-Harbour" is T, "Harbour" is H)
const LOCAL_LETTER = { WR_MAIN: 'W', WR_DAHANU: 'W', CR_MAIN: 'C', CR_HARBOUR: 'H', CR_TRANS: 'T', CR_PORT: 'P' }

export function modeName(mode) {
  return { LOCAL: 'Local train', METRO: 'Metro', MONORAIL: 'Monorail', WALK: 'Walk' }[mode] || mode
}

// The ink (dark or white) that reads better on an enamel colour
export function inkOn(hex) {
  const n = parseInt(hex.slice(1), 16)
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
  const L = 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255)
  const dark = 0.0098 // luminance of #0c1a26
  return (L + 0.05) / (dark + 0.05) > 1.05 / (L + 0.05) ? '#0C1A26' : '#FFFFFF'
}

export function station(id) {
  return stations[id] || { name: id.replace(/_/g, ' '), lat: null, lon: null, mode: 'LOCAL', line: null }
}

// Where a vehicle is heading, read off its shape id (SHP_<line>_<first>_TO_<last>_<hash>)
export function towards(leg) {
  const m = /_TO_(.+)_[0-9a-f]{4}$/.exec(leg.route_id || '')
  return m && stations[m[1]] ? stations[m[1]].name : null
}

// Minutes since midnight of the query day (1440+ = next day) -> "07:05"
export function clock(min) {
  const m = ((min % 1440) + 1440) % 1440
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

export const isNextDay = (min) => min >= 1440

export function duration(min) {
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}

export function nowMinutes() {
  const d = new Date()
  return d.getHours() * 60 + d.getMinutes()
}

export function toHHMM(min) {
  return clock(min)
}

export function fromHHMM(text) {
  const [h, m] = text.split(':').map(Number)
  return h * 60 + m
}

export function metres(m) {
  return m >= 950 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m / 10) * 10} m`
}

// ---- journeys ---------------------------------------------------------------

const vehicles = (journey) => journey.filter((l) => !l.is_walk).length

// The engine returns the Pareto front, fewest vehicles first and each journey arriving earlier than
// the one before. The two ends are what a commuter chooses between: the fastest journey and the one
// with the fewest changes. A "fewest changes" journey that arrives hours later (the last train has
// gone, so it leaves tomorrow) is no real alternative, so those are set apart as `slower`.
export function describeJourneys(routes) {
  if (!routes.length) return { shown: [], slower: [] }
  const items = routes.map((legs) => ({
    legs,
    depart: legs[0].dep_min,
    arrive: legs[legs.length - 1].arr_min,
    changes: Math.max(vehicles(legs) - 1, 0),
    walkMeters: legs.reduce((s, l) => s + (l.is_walk ? l.walk_m : 0), 0),
    labels: [],
  }))
  const fastest = items.reduce((a, b) => (b.arrive < a.arrive ? b : a))
  const allowance = Math.max(30, (fastest.arrive - fastest.depart) / 2)
  const near = items.filter((i) => i.arrive <= fastest.arrive + allowance)
  const slower = items.filter((i) => !near.includes(i))
  const fewest = near.reduce((a, b) => (vehicles(b.legs) < vehicles(a.legs) ? b : a))
  fastest.labels.push('Fastest')
  fewest.labels.push('Fewest changes')
  // fastest first, then fewest changes, then anything in between
  const shown = [fastest, ...(fewest !== fastest ? [fewest] : []), ...near.filter((i) => i !== fastest && i !== fewest)]
  return { shown, slower }
}

// A journey as alternating stops and legs, for the step-by-step view. Each stop knows when you arrive
// and when you leave, and whether you change vehicles there.
export function buildSteps(legs, queryMinutes) {
  const steps = []
  legs.forEach((leg, i) => {
    const next = legs[i + 1]
    if (i === 0) steps.push({ type: 'stop', id: leg.from, first: true, dep: leg.dep_min, down: leg, wait: leg.dep_min - queryMinutes })
    steps.push({ type: 'leg', leg })
    steps.push({
      type: 'stop', id: leg.to, last: !next, arr: leg.arr_min, dep: next ? next.dep_min : null,
      up: leg, down: next || null, wait: next ? next.dep_min - leg.arr_min : 0,
      change: Boolean(next) && !leg.is_walk && !next.is_walk,
    })
  })
  return steps
}
