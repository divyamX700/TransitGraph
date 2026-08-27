# TransitGraph (BomRouter)

TransitGraph is a high-performance multi-modal public transit routing engine and interface designed for the Mumbai suburban rail and metro networks.

Standard routing algorithms (such as Dijkstra or A*) compute single-criterion shortest paths based purely on travel time, frequently yielding fragile routes with impractical transfer windows. TransitGraph implements the **RAPTOR** (Round-Based Public Transit Routing) algorithm to generate **Pareto-optimal** journey sets, optimizing simultaneously for earliest arrival time and minimal trip transfers.

---

## Architecture Overview

The system is organized into three decoupled layers:

```
[ React Client ] 
       │  HTTP / JSON
       ▼
[ Node.js API Layer ] ── (In-memory Prefix Trie for O(m) Station Autocomplete)
       │  IPC (stdin / stdout pipes)
       ▼
[ C++ RAPTOR Engine ] ── (Contiguous GTFS Arrays + O(1) LRU Query Cache)
```

### 1. C++ Routing Core (`engine/`)
* **Algorithm:** Implements RAPTOR (Delling et al.), relaxing routes round-by-round ($k$-th round corresponds strictly to journeys with $k-1$ transfers).
* **Memory Layout:** Parses GTFS data into flattened `std::vector` structures (Structure of Arrays) to maximize CPU cache locality and eliminate pointer-chasing during graph traversal.
* **Timetable Lookup:** Uses $O(\log T)$ binary search over sorted departure arrays to identify the earliest valid trip at any boarded stop.
* **Footpath Modeling:** Models physical walking transfers between disconnected modal stations (e.g., Suburban Rail to Metro) using a Compressed Sparse Row (CSR) adjacency matrix.
* **LRU Cache:** An internal $O(1)$ Least Recently Used cache (hash map + doubly linked list) to memoize high-frequency commuter queries.

### 2. API Middleware (`api/`)
* **Process Multiplexing:** Supervises a persistent C++ child process and routes asynchronous HTTP queries across standard input/output streams via custom request correlation IDs, avoiding network serialization overhead between the server and the core engine.
* **Station Search Index:** Houses an in-memory Prefix Trie providing $O(m)$ prefix search for station lookups where $m$ is the query string length.

### 3. Web Interface (`web/`)
* **Frontend Stack:** React, Vite, Leaflet.
* **Map Optimization:** Transit line geometries (extracted from OpenStreetMap) are bundled as static GeoJSON and loaded once on client initialization. Route responses pass lightweight line identifiers rather than full coordinate sets.

### 4. Data Engineering Pipeline (`scripts/`)
* **GTFS Ingestion:** Python scripts parse unstructured timetable PDFs and schedule data into normalized GTFS feeds (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `shapes.txt`).
* **Midnight Rollover:** Employs a 48-hour schedule duplication (+1440 minute offset) to eliminate modulo arithmetic edge cases for overnight journeys spanning past 00:00.

---

## Benchmarks

Measurements taken across 1,000 randomized non-cached origin-destination queries through the full Node.js $\leftrightarrow$ C++ IPC pipeline on an x86_64 host:

| Metric | Latency |
|---|---|
| **Average Latency** | 2.78 ms |
| **p50 Latency** | 2.29 ms |
| **p95 Latency** | 3.72 ms |
| **p99 Latency** | 25.56 ms |
| **Min Latency** | 0.81 ms |

---

## Directory Structure

```
├── api/            # Express.js API supervisor and Prefix Trie index
├── data/           # Normalized GTFS dataset and station mappings
├── docs/           # Architecture Decision Records (ADRs) and specs
├── engine/         # C++ RAPTOR engine, GTFS parser, and LRU cache
├── scripts/        # Data extraction, normalization, and benchmark scripts
└── web/            # React frontend and Leaflet visualization
```

---

## Build and Installation

### Prerequisites
* C++17 compatible compiler (`g++`, `clang++`, or MSVC)
* Node.js (v18+)

### 1. Build Core Engine
```bash
cd engine
g++ -O3 -std=c++17 src/main.cpp src/raptor.cpp src/gtfs_parser.cpp -o raptor.exe
```

### 2. Start API Service
```bash
cd api
npm install
node server.js
```
The API server initializes and listens on `http://localhost:3000`.

### 3. Start Frontend Development Server
```bash
cd web
npm install
npm run dev
```
The client will be accessible at `http://localhost:5173`.

---

## Architecture Documentation

Technical rationale and trade-offs for all core components are documented in the [Architecture Decision Records (ADRs)](docs/decisions/):
* `0001-language-and-tech-stack.md`
* `0002-data-formats-and-gtfs.md`
* `0003-algorithm-selection.md`
* `0004-data-structures-and-memory.md`
* `0005-backend-implementation-details.md`
