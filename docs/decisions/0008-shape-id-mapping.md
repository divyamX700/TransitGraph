# ADR-0008: Shape ID to Route Mapping

## Status
Accepted

## Date
2026-08-08

## Context
Rendering the transit map in the frontend requires associating the physical polyline shapes (`shapes.txt`) with their respective transit lines (`route_id`). However, the official GTFS `trips.txt` file contains misfiled lines (e.g., Uran/Port line trips are incorrectly labeled as `CR_MAIN`). Relying strictly on relational mapping from `trips.txt` causes visual bugs where the wrong lines light up during routing.

## Decision
Bypass `trips.txt` for determining the `route_id` of a map shape. Instead, use a deterministic string-parsing function (`routeIdFromShapeId`) in `server.js` that extracts the correct route directly from the `shape_id` string itself (e.g., `SHP_CR_PORT_...` definitively becomes `CR_PORT`).

## Consequences
- The frontend map accurately colors and highlights the correct transit lines, isolating the visual layer from bad GTFS relational data.
- The C++ backend routing engine remains unaffected, as it strictly routes based on the timetable stop sequences rather than visual shape mapping.
