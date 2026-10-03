const API = import.meta.env.VITE_API_URL || ''

async function getJson(path, signal) {
  let res
  try {
    res = await fetch(`${API}${path}`, { signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Could not reach the journey server. Check your connection')
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error || `The journey server is not responding (${res.status})`)
  return body
}

export const fetchStations = () => getJson('/api/stations')
export const fetchLines = () => getJson('/api/lines')
export const fetchShapes = () => getJson('/api/shapes')
export const searchStations = (prefix, signal) => getJson(`/api/stations?prefix=${encodeURIComponent(prefix)}`, signal)
export const findRoutes = (from, to, minutes, signal) =>
  getJson(`/api/route?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&time=${minutes}`, signal)
