# ADR-0007: Node.js LRU Cache for Routing

## Status
Accepted

## Date
2026-08-08

## Context
The C++ RAPTOR engine is highly optimized, but running the algorithm for the exact same query (same source, destination, and time) repeatedly is redundant and computationally wasteful. Under load, identical queries (e.g., popular commuter routes at 09:00 AM) would unnecessarily lock the C++ engine via the IPC pipeline.

## Decision
Implement a custom Least Recently Used (LRU) Cache in the Node.js API layer (`api/lru.js`) to cache route results before forwarding queries to the C++ engine.
- Built from scratch using a Hash Map and Doubly Linked List for strict `O(1)` get, set, and eviction.
- Capacity is capped at 500 entries to bound memory usage.
- Eviction is strictly capacity-based; no Time-To-Live (TTL) is needed because timetable routing for a specific static time parameter is deterministic.

## Consequences
- Protects the C++ engine from redundant queries.
- Improves API response times to near-zero for cached hits.
- Adds state to the Node server, meaning the cache will reset if the Node process restarts (acceptable trade-off).
