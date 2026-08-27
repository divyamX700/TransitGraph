# TransitGraph — Metro & Monorail Expansion Plan

## Overview

This document is the **complete, authoritative engineering plan** for expanding TransitGraph from Mumbai Local trains only to a **multi-modal network** including:
- Mumbai Metro (all operational lines)
- Mumbai Monorail (1 operational line)
- **Walking transfers** between physically separate Local and Metro/Monorail stations

The plan is written to be unambiguous. Any engineer or AI agent reading it must know **exactly** what to research, decide, build, or validate at each step — with no assumed context beyond what is written here.

---

## Current System State (Baseline)

Before reading the plan, understand what exists:

| Layer | What exists |
|---|---|
| Data | GTFS files for Mumbai Local trains only: `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `shapes.txt` |
| Engine (C++) | `GTFSParser` reads a single GTFS directory → builds `RaptorData`. RAPTOR runs on a single unified stop/route namespace. Footpaths (walking links) do NOT exist. |
| Transfer model | Fixed 5-minute in-station penalty in `raptor.h` (`TRANSFER_PENALTY_MINS = 5`). No cross-mode walking. |
| API (Node.js) | `api/server.js` spawns the C++ binary, sends queries via `stdin`, receives JSON. Single GTFS path (`data/gtfs`). |
| UI (React) | Station autocomplete (Trie), route cards, Leaflet map. Map coloring uses `shape_id` string parsing. Knows nothing about metro. |

**Critical constraint:** The current `RaptorData` struct has no concept of footpaths (walking edges between distinct stops). This must be added.

---

## Phase 0 — Research and Decisions (Before Any Code)

### 0.1 Determine All Operational Metro Lines

Research and document the following for each operational Mumbai Metro line:

| Required fact | Source |
|---|---|
| Line number and official name | MMRDA / official website |
| Terminal stations (north and south end) | MMRDA |
| All intermediate stations, in order | MMRDA |
| Operational status (open vs under construction) | Current news, MMRDA |
| Operator (MahaMetro, MMRDA, etc.) | MMRDA |
| Frequency / headway (peak and off-peak) | Official timetable if available |
| First train / last train times | Official timetable |

**Lines to research (as of 2025):**
- Line 1: Versova–Andheri–Ghatkopar (VAG)
- Line 2A: Dahisar (E)–D.N. Nagar
- Line 2B: D.N. Nagar–Mandale (verify operational status)
- Line 3: Colaba–BKC–Aarey (Underground — verify which sections are open)
- Line 7: Andheri (E)–Dahisar (E)
- Line 7A: Andheri (E)–CSMT (verify status)
- Monorail: Sant Gadge Maharaj Chowk–Wadala–Jacob Circle

**Output:** A structured station list per line with sequence order. This is the raw dataset for Phase 1.

### 0.2 Determine Walking Interchanges

Walking interchanges are pairs of (Local station, Metro station) close enough to serve as interchange points on foot.

**Process:**
1. For every Metro station, identify the nearest Local station by name or geography.
2. Measure walking distance/time using Google Maps walking directions or OpenStreetMap Overpass API.
3. Classify into tiers:
   - **Tier A (<=5 min walk, <=400m):** Model as 5-minute footpath
   - **Tier B (5–12 min walk, 400–800m):** Model as actual measured time
   - **Tier C (>12 min, >800m):** Do NOT model — too far to be practical
4. Document each interchange: Local stop ID, Metro stop ID, walking time (minutes), source of measurement.

**Known high-confidence interchanges to verify:**
- Andheri (Local) <-> Andheri (Line 1) <-> Andheri (Line 2A/7)
- Ghatkopar (Local) <-> Ghatkopar (Line 1)
- Matunga Road (Local) <-> nearest Monorail station?
- BKC (Line 3) — no direct Local, nearest local station?

**Output:** A CSV file `data/footpaths.csv` with columns: `from_stop_id, to_stop_id, min_transfer_time` (minutes). One row per directed edge. All walking transfers are bidirectional — generate both directions.

### 0.3 Write ADR-009: Multi-Modal Expansion Strategy

Before writing any code, write `docs/decisions/0009-multimodal-expansion.md` covering:
- Decision to expand to Metro + Monorail
- Decision to model walking transfers via explicit footpath edges
- Decision on walking time thresholds (Tier A/B/C)
- Decision on unified GTFS merge strategy
- Alternatives considered for footpath modelling

---

## Phase 1 — Data Engineering

### 1.1 Produce GTFS for Metro and Monorail

**Goal:** Generate valid GTFS files for all operational Metro/Monorail lines.

**Required files per mode:**
- `agency.txt` — operator name, URL, timezone (`Asia/Kolkata`)
- `routes.txt` — one row per metro line. `route_type` = 1 (Metro) or 0 (Tram/Monorail). `route_color` must match official line color.
- `stops.txt` — one row per station. `stop_id` must be namespace-prefixed (see below). `stop_lat`/`stop_lon` must be real coordinates.
- `trips.txt` — one row per train service. Use `direction_id` 0/1 for up/down.
- `stop_times.txt` — departure and arrival time for every stop on every trip.
- `shapes.txt` — polyline coordinates per route. Source from OpenStreetMap (metro track geometries are available).
- `calendar.txt` — service days (typically all 7 days for metro).

**ID namespacing rules (CRITICAL — prevents stop_id collisions):**

Every `stop_id` and `route_id` in metro/monorail GTFS must be prefixed:
- Local trains: existing IDs unchanged (`CSMT`, `DADAR_W`, etc.)
- Metro Line 1: `M1_VERSOVA`, `M1_ANDHERI`, `M1_GHATKOPAR`, etc.
- Metro Line 2A: `M2A_DAHISAR_E`, `M2A_DN_NAGAR`, etc.
- Metro Line 3: `M3_COLABA`, `M3_BKC`, etc.
- Metro Line 7: `M7_ANDHERI_E`, etc.
- Monorail: `MR_WADALA`, `MR_JACOB_CIRCLE`, etc.

**Synthetic timetable generation (if exact data unavailable):**

If only headway + first/last train is known, generate synthetic trips:
```
first_train = 06:00
last_train  = 23:00
headway     = 10 minutes (peak), 15 minutes (off-peak)

For each direction:
  For each departure_time from first_train to last_train, step by headway:
    Generate one trip
    Compute arrival/departure at each stop using:
      inter-station travel time = ~2 minutes (estimate, document assumption)
      dwell time = 0:30 minutes per stop
```

Document the inter-station time estimate explicitly as an assumption.

**Validation checklist after generating GTFS:**
- [ ] All `stop_id` in `stop_times.txt` exist in `stops.txt`
- [ ] All `trip_id` in `stop_times.txt` exist in `trips.txt`
- [ ] All `route_id` in `trips.txt` exist in `routes.txt`
- [ ] Stop times within each trip are strictly increasing
- [ ] No duplicate `stop_id` across local + metro GTFS combined
- [ ] Real lat/lon for all stops (not 0.0, 0.0)

### 1.2 Produce `footpaths.csv`

From Phase 0.2 research, produce `data/footpaths.csv`:

```
from_stop_id,to_stop_id,min_transfer_time
ANDHERI,M1_ANDHERI,7
M1_ANDHERI,ANDHERI,7
GHATKOPAR,M1_GHATKOPAR,5
M1_GHATKOPAR,GHATKOPAR,5
```

`min_transfer_time` is integer minutes. The file is directed — both directions must be present for each walking pair.

### 1.3 Merge GTFS into a Unified Dataset

Write a Python script `data/scripts/merge_gtfs.py` that:
1. Reads `data/gtfs/` (local trains — source of truth, unchanged)
2. Reads `data/metro_gtfs/` and `data/monorail_gtfs/`
3. Concatenates all `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `shapes.txt` (skip header line on each concatenation)
4. Writes merged output to `data/merged_gtfs/`

This keeps the C++ engine interface unchanged (still reads one directory).

**Validation after merge:**
- Row count of merged file = sum of individual file row counts (minus redundant headers)
- No duplicate `stop_id` or `route_id` in merged output

---

## Phase 2 — Engine Changes (C++)

This is the most critical phase. The RAPTOR algorithm must be extended with footpath support exactly as described in the original RAPTOR research paper.

### 2.1 Add Footpath Data Structures to `raptor_types.h`

Add a `Footpath` struct and extend `RaptorData`:

```cpp
struct Footpath {
    uint32_t target_stop_idx;
    int      walking_time_mins;
};

// In RaptorData, add:
// footpaths_offset[i] and footpaths_offset[i+1] delimit the footpaths from stop i.
// This is Compressed Sparse Row (CSR) format — same pattern as stop_routes already uses.
std::vector<uint32_t> footpaths_offset; // length = num_stops + 1
std::vector<Footpath> footpaths;        // all walking edges
```

Also add `TransitMode` to `Stop` and `Route`:

```cpp
enum class TransitMode : uint8_t { LOCAL = 0, METRO = 1, MONORAIL = 2 };

struct Stop {
    std::string  id;
    std::string  name;
    TransitMode  mode;                // NEW
    uint32_t     stop_routes_offset;
    uint32_t     stop_routes_count;
};

struct Route {
    std::string  id;
    TransitMode  mode;                // NEW
    uint32_t     route_stops_offset;
    uint32_t     num_stops;
    uint32_t     stop_times_offset;
    uint32_t     num_trips;
};
```

### 2.2 Extend `GTFSParser` for Footpaths and Mode

In `gtfs_parser.cpp`:

**Parse `route_type` from `routes.txt`** to set `Route::mode`:
- `route_type == 2` → `TransitMode::LOCAL`
- `route_type == 1` → `TransitMode::METRO`
- `route_type == 0` or `12` → `TransitMode::MONORAIL`

**Add `GTFSParser::load_footpaths(path, data)`:**
1. Open `footpaths.csv`, skip header
2. For each row: resolve `from_stop_id` → index, `to_stop_id` → index using `data.stop_id_to_index`
3. If either ID not found: print warning to `stderr`, skip row. Do NOT crash.
4. Build temporary grouped edges: `std::vector<std::vector<Footpath>> grouped(num_stops)`
5. Convert to CSR format into `data.footpaths_offset` and `data.footpaths`

Call `load_footpaths` at the end of `GTFSParser::parse()` — after all stops are indexed.

### 2.3 Extend RAPTOR Algorithm for Footpaths (Core Change)

The RAPTOR paper prescribes footpath handling as a post-route-traversal relaxation in each round.

**Current round loop (pseudocode):**
```
for k = 1 to MAX_ROUNDS:
  Step A: Collect routes Q serving marked stops
  Step B: Traverse each route, update tau[k][p]
  Step C: [MISSING]
  Step D: Check target, record pareto journey
```

**New round loop:**
```
for k = 1 to MAX_ROUNDS:
  Step A: Collect routes Q serving marked stops    (unchanged)
  Step B: Traverse each route, update tau[k][p]   (unchanged)
  Step C: Footpath relaxation — NEW:
    for each stop p (0 to num_stops-1):
      if tau[k][p] was improved this round:
        for each footpath (p -> q, walk_time) in footpaths[p]:
          candidate = tau[k][p] + walk_time
          if candidate < tau_star[q]:
            tau[k][q] = candidate
            tau_star[q] = candidate
            parents[k][q] = { LegType::WALK, source=p, walking_time=walk_time }
            marked[q] = true
  Step D: Check target, record pareto journey     (unchanged)
```

**Tracking which stops improved in Step B:** Maintain a local `std::vector<uint32_t> improved_this_round` that accumulates stop indices improved during Step B. In Step C, iterate only over `improved_this_round` (not all stops) for efficiency.

### 2.4 Extend `ParentPointer` and `JourneyLeg` for Walk Legs

```cpp
enum class LegType : uint8_t { TRANSIT = 0, WALK = 1 };

struct ParentPointer {
    LegType   leg_type         = LegType::TRANSIT;
    uint32_t  boarded_stop_idx = UINT32_MAX;
    uint32_t  route_idx        = UINT32_MAX;  // unused if WALK
    uint32_t  trip_idx         = UINT32_MAX;  // unused if WALK
    int       walking_time     = 0;           // used only if WALK
};

struct JourneyLeg {
    std::string from_stop_id;
    std::string to_stop_id;
    std::string route_id;       // "WALK" for walk legs
    std::string trip_id;        // empty for walk legs
    std::string mode;           // "LOCAL", "METRO", "MONORAIL", or "WALK"
    int         departure_time;
    int         arrival_time;
    bool        is_walk;        // true if footpath leg
};
```

### 2.5 Update Journey Reconstruction for Walk Legs

In `raptor.cpp`, during path reconstruction (backtracking via `parents`):

```cpp
if (parents[curr_round][curr].leg_type == LegType::WALK) {
    JourneyLeg leg;
    leg.is_walk        = true;
    leg.mode           = "WALK";
    leg.route_id       = "WALK";
    leg.trip_id        = "";
    leg.to_stop_id     = data.stops[curr].id;
    leg.from_stop_id   = data.stops[parents[curr_round][curr].boarded_stop_idx].id;
    leg.arrival_time   = tau[curr_round][curr]; // when arrived at q
    leg.departure_time = leg.arrival_time - parents[curr_round][curr].walking_time;
    journey.push_back(leg);
    curr = parents[curr_round][curr].boarded_stop_idx;
    // Do NOT decrement curr_round — walk does not consume a round
} else {
    // Existing transit reconstruction logic unchanged
}
```

**Important:** Decrement `curr_round` only after a TRANSIT leg, not after a WALK leg. A walk within a round does not reduce the round counter.

### 2.6 Transfer Penalty — Walk vs Transit

The current 5-minute `TRANSFER_PENALTY_MINS` is applied during Step B (route boarding). It remains unchanged for same-stop cross-route transfers. For footpath edges (Step C), the penalty is NOT applied — the walking time already accounts for the inconvenience. The footpath's `walking_time_mins` is the full cost.

### 2.7 Extend JSON Output in `main.cpp`

Update `journeys_to_json` to include `is_walk` and `mode`:

```cpp
ss << "\"is_walk\": " << (leg.is_walk ? "true" : "false") << ", ";
ss << "\"mode\": \"" << leg.mode << "\", ";
```

Update `main.cpp` to accept footpaths path argument:

```cpp
string gtfs_dir       = argc > 1 ? argv[1] : "data/merged_gtfs";
string footpaths_path = argc > 2 ? argv[2] : "data/footpaths.csv";

RaptorData data = GTFSParser::parse(gtfs_dir);
GTFSParser::load_footpaths(footpaths_path, data);
Raptor raptor(data);
```

### 2.8 Engine Test Cases (Manual)

Before declaring engine complete, test the following via stdin:

1. **Direct metro trip:** Source and target on same metro line. Expect 1 transit leg, no walk.
2. **Local + walk + metro:** Source on Local, target on Metro. Expect: transit leg (local) + walk leg + transit leg (metro).
3. **Metro + walk + local:** Reverse of above.
4. **No route exists:** Source and target with no connection. Expect `[]`.
5. **Same station:** Source equals target. Expect `[]`.
6. **Midnight rollover with metro:** Query at 23:45 — engine must handle metro timetable in 48-hour window too.

---

## Phase 3 — API Layer Changes (Node.js)

### 3.1 Update Engine Spawn

In `api/server.js`, update spawn:

```js
const engine = spawn('./engine/build/transitgraph', [
  'data/merged_gtfs',
  'data/footpaths.csv'
])
```

### 3.2 Extend Autocomplete Trie with Metro Stops

The `PrefixTrie` loads local stop names from `stops.txt`. Extend it to load from merged `stops.txt`.

Metro stop names often overlap with local names (e.g., "Andheri"). The autocomplete must disambiguate:

```
Andheri (Local)
Andheri (Metro – Line 1)
Andheri (Metro – Line 7)
```

Each trie entry stores: `{ id, displayName, mode }`. The `id` sent to the engine is the namespaced stop ID (e.g., `M1_ANDHERI`). The `displayName` is what is shown to the user.

### 3.3 Stop ID Resolution

The API must resolve user-typed station names to exact stop IDs. With metro, multiple stops can share a base name. The user must select from disambiguated autocomplete options. The selected entry's `id` field is passed directly to the engine.

---

## Phase 4 — Frontend Changes (React)

### 4.1 Mode-Aware Line Colors

Add a `LINE_COLORS` lookup in `web/src/utils.js` (or new `web/src/lineColors.js`):

```js
export const LINE_COLORS = {
  // Local Trains (existing)
  WESTERN:   '#2563EB',
  CENTRAL:   '#DC2626',
  HARBOUR:   '#16A34A',

  // Metro (verify official colors from MMRDA)
  METRO_L1:  '#E11D48',  // VAG Line — verify
  METRO_L2A: '#F97316',  // verify
  METRO_L3:  '#7C3AED',  // verify (underground, often purple)
  METRO_L7:  '#D97706',  // verify

  // Monorail
  MONORAIL:  '#0891B2',  // verify

  // Walk leg
  WALK:      '#6B7280',  // neutral grey
}
```

**Important:** Verify every color against official MMRDA branding. Do NOT invent colors.

The color lookup function must use `route_id` prefix: parse the prefix from the route ID returned in the leg (e.g., `M1_...` → `METRO_L1`).

### 4.2 Walk Leg Rendering in Journey Diagram

Extend the expanded journey diagram in `RouteCard.jsx` to render walk legs:

Walk leg visual:
- Dashed grey vertical line (CSS: `border-left: 2px dashed var(--text-muted)`)
- Walking icon: use an SVG icon (phosphor-icons has a `Footprints` icon — use it)
- Text: `"~X min walk"` in italic, muted color
- No train badge, no platform number

```jsx
// In journey diagram render loop:
if (leg.is_walk) {
  return <WalkLeg key={i} leg={leg} />
} else {
  return <TransitLeg key={i} leg={leg} />
}
```

### 4.3 Mode Badge on Route Cards

Each route card's line bar (the colored segments at bottom) must now correctly color metro segments by their mode color, not just local line color.

Add `mode` to the data passed to `RouteCard` and use `LINE_COLORS[mode]` for each segment.

### 4.4 Map Layer for Metro Shapes

Extend `MapView.jsx` to draw metro polylines from `shapes.txt` in `data/merged_gtfs/`. Metro lines should be visually distinct:
- Local: solid line, 3px
- Metro: solid line, 3px, correct metro color
- Monorail: dashed line, 2px (to visually signal elevated mono structure)

### 4.5 Station Autocomplete — Mode Labels

Update `StationInput.jsx` to show mode labels as a badge or suffix in each autocomplete item:

```
Andheri (Local)       [Western]
Andheri (Metro L1)    [Line 1 – VAG]
Andheri (Metro L7)    [Line 7]
```

The `mode` field comes from the API autocomplete response.

---

## Phase 5 — Validation

### 5.1 Routing Correctness Tests (Manual)

Test real journeys against expected behavior:

| From | To | Expected behavior |
|---|---|---|
| Andheri (Local) | Ghatkopar (Local) | Direct Central Local (no metro needed) |
| Versova (Metro L1) | Ghatkopar (Metro L1) | Metro Line 1 direct |
| Churchgate | BKC (Metro L3) | Complex multi-modal — verify manually |
| Dadar (Local) | Andheri (Metro L2A) | Local + walk or local direct? Verify. |

For each test: compare engine output against manually researched correct answer. Any mismatch = bug.

### 5.2 Data Completeness Validation Script

Write `data/scripts/validate_merged.py`:
1. Load merged `stops.txt` and `footpaths.csv`
2. For every footpath edge, check both stop IDs exist in `stops.txt` → error if not
3. For every metro station, check at least one footpath exists (warn if isolated from local network — this may be intentional)
4. For every stop in `stops.txt`, check at least one route serves it (orphaned stops = data error)
5. Print pass/fail summary

### 5.3 48-Hour Rollover With Metro

The existing 48-hour timetable duplication in `GTFSParser` (adding 1440 to all stop times) must also be applied to metro trips. Verify this is done correctly after merge — metro late-night trips must also be duplicated.

---

## Phase 6 — Documentation Updates

### 6.1 Update ADR-001

Add: routing objectives now apply to multi-modal network. Clarify walk legs do NOT add a transfer round in RAPTOR (a walk + re-board = 1 transfer, not 2). This follows from RAPTOR algorithm structure where footpaths are relaxed within a round.

### 6.2 Update ADR-003

Add: footpath support follows the RAPTOR paper's prescribed footpath relaxation step, added in Phase 2. Cite: Delling, Pajor, Werneck (2012), "Round-Based Public Transit Routing."

### 6.3 Update ADR-004

Add: unified GTFS merge strategy, `footpaths.csv` format, stop ID namespacing convention.

### 6.4 Update ADR-005

Add: footpath CSR data structure, `ParentPointer` extension for walk legs, `LegType` enum, `TransitMode` enum.

### 6.5 Write ADR-009 (Multi-Modal Expansion)

As defined in Phase 0.3.

### 6.6 Update `docs/data-sources.md`

Add: sources for Metro GTFS data (MMRDA website, manually constructed synthetic timetables, OpenStreetMap shapes).

---

## Complete File Change Summary

| File | Change | Description |
|---|---|---|
| `data/scripts/merge_gtfs.py` | NEW | Merge local + metro GTFS → `data/merged_gtfs/` |
| `data/footpaths.csv` | NEW | Walking edges between Local and Metro/Monorail stops |
| `data/metro_gtfs/*.txt` | NEW | GTFS for all Metro lines |
| `data/monorail_gtfs/*.txt` | NEW | GTFS for Monorail |
| `data/scripts/validate_merged.py` | NEW | Validates merged GTFS + footpaths integrity |
| `engine/src/raptor_types.h` | MODIFY | Add `Footpath`, `TransitMode`, `LegType`; extend `Stop`, `Route`, `JourneyLeg`, `ParentPointer` |
| `engine/src/gtfs_parser.cpp` | MODIFY | Parse `route_type` → `TransitMode`; add `load_footpaths` |
| `engine/src/gtfs_parser.h` | MODIFY | Declare `load_footpaths` |
| `engine/src/raptor.cpp` | MODIFY | Add footpath relaxation step; extend reconstruction for walk legs |
| `engine/src/main.cpp` | MODIFY | Accept footpaths arg; add `is_walk`, `mode` to JSON output |
| `api/server.js` | MODIFY | Update spawn args; load metro stops in Trie with mode labels |
| `web/src/utils.js` | MODIFY | Add `LINE_COLORS` map keyed by mode/route prefix |
| `web/src/RouteCard.jsx` | MODIFY | Render walk legs with dashed style + icon |
| `web/src/MapView.jsx` | MODIFY | Draw metro/monorail shapes on map |
| `web/src/StationInput.jsx` | MODIFY | Show mode badge in autocomplete items |
| `web/src/index.css` | MODIFY | Walk leg dashed styling; metro line color CSS tokens |
| `docs/decisions/0009-multimodal-expansion.md` | NEW | ADR for this expansion |
| `docs/decisions/0001-routing-objectives.md` | MODIFY | Update per Phase 6.1 |
| `docs/decisions/0003-algorithm-selection.md` | MODIFY | Update per Phase 6.2 |
| `docs/decisions/0004-data-model.md` | MODIFY | Update per Phase 6.3 |
| `docs/decisions/0005-backend-implementation-details.md` | MODIFY | Update per Phase 6.4 |

---

## Open Questions Requiring Decision Before Starting Phase 2

1. **Walking threshold:** Include Tier B (5–12 min) interchanges or only Tier A (<=5 min)?
2. **Synthetic timetables:** If exact Metro timetable unavailable, are headway-based synthetic trips acceptable?
3. **Metro lines at launch:** All operational lines, or start with Line 1 only and expand?
4. **Walk + re-board = 1 transfer (confirmed above)?** Approve before engine changes begin.

> [!IMPORTANT]
> Do NOT start Phase 1 or Phase 2 until Phase 0 research (walking interchange table) is complete. The footpath data is the correctness foundation for everything else.
