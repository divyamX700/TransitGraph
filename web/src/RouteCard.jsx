import { getLineColor, getLineName, duration } from './utils.js'
import { LineBadge } from './components.jsx'

function JourneyDiagram({ legs }) {
  return (
    <div className="journey-diagram">
      {legs.map((leg, i) => {
        const color = getLineColor(leg.route_id)
        const isLast = i === legs.length - 1
        const isTransfer = i < legs.length - 1

        return (
          <div key={i}>
            {/* Board stop */}
            <div className="journey-leg">
              <div className="journey-line-track">
                <div className="journey-dot terminus" style={{ '--line-color': color }} />
                <div className="journey-track-line" style={{ '--line-color': color }} />
              </div>
              <div className="journey-content">
                <div className="journey-station">{leg.from.replace(/_/g, ' ')}</div>
                <div className="journey-meta">dep {leg.dep}</div>
                <div className="journey-train-info">
                  <LineBadge routeId={leg.route_id} />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Train {leg.trip_id}
                  </span>
                </div>
              </div>
            </div>

            {/* Alight stop */}
            <div className="journey-leg">
              <div className="journey-line-track">
                <div className="journey-dot terminus" style={{ '--line-color': color }} />
                {isTransfer && <div className="journey-transfer-gap" />}
              </div>
              <div className="journey-content">
                <div className="journey-station">{leg.to.replace(/_/g, ' ')}</div>
                <div className="journey-meta">arr {leg.arr}</div>
                {isTransfer && (
                  <div className="transfer-label">Walk 5 min · change to {getLineName(legs[i+1]?.route_id)}</div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function RouteCard({ route, index, isActive, onSelect, onHover }) {
  const firstLeg = route[0]
  const lastLeg = route[route.length - 1]
  const transfers = route.length - 1
  const totalDuration = duration(firstLeg.dep, lastLeg.arr)
  const primaryColor = getLineColor(firstLeg.route_id)

  return (
    <div
      className={`route-card${isActive ? ' active' : ''}`}
      style={{ '--line-color': primaryColor }}
      onClick={() => onSelect(index)}
      onMouseEnter={() => onHover(index)}
      onMouseLeave={() => onHover(null)}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onSelect(index)}
      aria-pressed={isActive}
    >
      <div className="route-card-top">
        <div className="route-endpoints">
          {firstLeg.from.replace(/_/g, ' ')} → {lastLeg.to.replace(/_/g, ' ')}
        </div>
        <div className="route-transfers">
          {transfers === 0 ? 'Direct' : `${transfers} change${transfers > 1 ? 's' : ''}`}
        </div>
      </div>

      <div className="route-times">
        <span className="route-time">{firstLeg.dep}</span>
        <span className="route-duration">{totalDuration}</span>
        <span className="route-time">{lastLeg.arr}</span>
      </div>

      <div className="route-line-bar">
        {route.map((leg, i) => (
          <div
            key={i}
            className="route-line-segment"
            style={{ background: getLineColor(leg.route_id) }}
          />
        ))}
      </div>

      {isActive && <JourneyDiagram legs={route} />}
    </div>
  )
}
