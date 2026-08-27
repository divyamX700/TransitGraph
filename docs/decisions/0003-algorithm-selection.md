# ADR-003: Routing Algorithm Selection

## Status
Accepted

## Date
2026-08-06

## Context
BomRouter needs to calculate Pareto-optimal routes (optimizing for both Earliest Arrival Time and minimum number of transfers) over a scheduled transit network. Traditional graph algorithms like Dijkstra are slow on massive time-expanded graphs, and Connection Scan Algorithm (CSA) is optimized primarily for earliest arrival time, not multi-criteria Pareto sets.

## Decision
We will implement **RAPTOR (Round-Based Public Transit Routing)** in the C++ engine. RAPTOR operates in rounds corresponding to the number of transfers, making it natively suited for Pareto-optimal multi-objective routing.

## Alternatives Considered
- **Time-Expanded Dijkstra:** Rejected due to massive graph size and slow execution for multi-objective searches.
- **Connection Scan Algorithm (CSA):** Rejected because adapting it to find Pareto-optimal routes (Multi-Criteria CSA) loses much of its elegant simplicity, whereas RAPTOR is purpose-built for this exact requirement.

## Consequences
- The data engineering pipeline must generate data structured in a way that RAPTOR can consume (arrays of Routes, RouteStops, and Trips).
- We will rely on the official RAPTOR research paper to guide the C++ implementation.
