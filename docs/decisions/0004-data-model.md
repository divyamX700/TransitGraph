# ADR-004: Data Model and Export Format

## Status
Accepted

## Date
2026-08-06

## Context
The Python data engineering pipeline must extract timetable data from PDFs and export it in a structured format for the C++ engine to consume. Furthermore, the React frontend requires geographical data to accurately draw the train routes on a map, rather than just drawing straight lines between stations.

## Decision
We will adopt the **GTFS (General Transit Feed Specification)** format as our intermediate data model.
The Python pipeline will generate standard GTFS CSV files, including `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, and specifically `shapes.txt`.

## Alternatives Considered
- **Custom JSON format:** Rejected. A custom JSON format would require reinventing a schema for timetables. It also provides no standardized way to handle geographical shapes for map rendering.

## Consequences
- The C++ engine must include a CSV parser to read GTFS files and construct the RAPTOR internal data structures.
- The UI can leverage `shapes.txt` to draw highly realistic polylines along the actual train tracks.
