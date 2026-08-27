# ADR-005: Backend Implementation Details (Data Structures & Edge Cases)

## Status
Accepted

## Date
2026-08-06

## Context
During the implementation of the Phase 4 RAPTOR routing engine and the Node.js API boundary, several specific architectural and data-structure decisions were made to handle edge cases in the Mumbai Local dataset and to elevate the engineering quality of the project for interview settings.

## Decision

1. **Transfer Penalty:** 
   We enforce a strict 5-minute fixed walking penalty when transferring between routes at interchange stations (like Dadar). This is implemented directly in the RAPTOR round loop by requiring the departure time of the catching trip to be $\ge \tau_{k-1}(p) + 5 \text{ mins}$.
2. **Midnight Rollover (48-Hour Window):** 
   To handle queries late at night and trains that arrive past midnight, the GTFS parser duplicates the entire timetable schedule, adding 1440 minutes (24 hours) to all stop times. This creates a seamless 48-hour routing window, avoiding complex modulo arithmetic during graph traversal.
3. **Prefix Trie (Node.js):** 
   Station name autocompletion is handled by a custom `PrefixTrie` class in Node.js, providing $O(m)$ lookup time.
4. **LRU Cache (C++):** 
   The C++ engine uses a custom `LRUCache` (Hash Map + Doubly Linked List) to memoize the JSON results of frequent queries. This bypasses the algorithm entirely on cache hits, reducing compute load to $O(1)$.

## Consequences
- The GTFS parser uses slightly more memory to hold the 48-hour duplicated trips, but since the Mumbai network is small (~6000 trips after duplication), this is entirely negligible for a modern C++ process.
- The `LRUCache` and `PrefixTrie` demonstrate strong, classical data structure fundamentals suitable for technical interviews.
- The 5-minute penalty successfully prevents the routing algorithm from suggesting physically impossible 1-minute platform changes.
