import { getLineColor, getLineName } from './utils.js'

export function LineBadge({ routeId }) {
  const color = getLineColor(routeId)
  const name = getLineName(routeId)
  if (!name) return null
  return (
    <span className="line-badge" style={{ '--line-color': color }}>
      <span className="line-badge-dot" />
      {name}
    </span>
  )
}

export function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton" style={{ height: 14, width: '60%' }} />
      <div className="skeleton" style={{ height: 24, width: '80%' }} />
      <div className="skeleton" style={{ height: 10, width: '100%' }} />
    </div>
  )
}
