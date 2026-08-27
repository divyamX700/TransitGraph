# ADR-001: Routing Objectives and Core Features

## Status
Accepted

## Date
2026-08-06

## Context
Before designing the system architecture for the BomRouter engine, we need to define the core product features and routing objectives. The Mumbai Local train network is highly complex, and standard routing algorithms (which optimize purely for time) often suggest impractical routes that involve stressful transfers during peak hours. Furthermore, commuters often have strong preferences regarding train types (e.g., AC trains, Fast vs. Slow trains) and typically plan their journeys moving forward from a specific departure time.

## Decision
We will build the routing engine and interface with the following product features:

1. **Routing Objective (Pareto-Optimal Set):** Instead of returning a single "fastest" route, the engine will return a Pareto-optimal set of routes, allowing the user to choose their preferred trade-off between minimum travel time and minimum number of transfers.
2. **Query Strategy (Forward Search):** The engine will support "Leave Now" (defaulting to current time) and "Leave At" (user-specified time) queries. Backward searching ("Arrive By") is excluded from Phase 1 to limit algorithmic complexity.
3. **Train Filters:** Users will have explicit toggles to filter for "AC Trains Only" or "Prefer Fast Trains". By default, no filters are applied.
4. **UI Presentation:** 
   - The interface will show the calculated optimal routes.
   - Upon selecting a route, the UI will display the immediate upcoming trains for that path.
   - Train entries will be badged with clear markers indicating if they are Fast or AC.
   - A simplified visual diagram (e.g., A -> B, walk to B', B' -> C) will be provided for clarity on transfers.
5. **Transfer Dynamics (Fixed Penalty):** To avoid overcomplicating data ingestion, transfers between lines will be modeled with a fixed time penalty rather than station-specific walking times.

## Alternatives Considered
- **Strictly Earliest Arrival Time:** Rejected. Optimizing purely for time often results in recommending unnecessary and stressful transfers, which is a poor experience on the Mumbai Local network.
- **Bidirectional Search ("Arrive By" queries):** Rejected for Phase 1. It adds significant algorithmic complexity to the C++ engine (requiring reverse graph traversal) and is less critical for an MVP.
- **Agnostic Train Routing (No Filters):** Rejected. Fast vs. Slow and AC vs. Non-AC are fundamental choices for Mumbai commuters; ignoring them degrades the utility of the application.
- **Station-Specific Transfer Times:** Rejected. Manually mapping accurate walking times for every interchange station adds unnecessary data engineering complexity for Phase 1 without a proportionate gain in algorithmic demonstration.

## Consequences
- The C++ routing engine must implement a Multi-Objective Shortest Path algorithm (or equivalent) rather than a simple Dijkstra's algorithm.
- The engine's graph representation must support dynamic edge filtering during traversal to handle the AC/Fast toggles.
- The React frontend will require components for interactive route selection, badging, and a custom interchange visualization diagram.
