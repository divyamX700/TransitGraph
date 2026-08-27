# ADR-002: System Architecture Boundaries (C++ and Node.js Integration)

## Status
Accepted

## Date
2026-08-06

## Context
BomRouter consists of a C++ routing engine and a Node.js/React frontend. We need a method for the Node.js API to pass routing queries to the C++ engine and receive JSON results, while balancing performance, deployment simplicity, and architectural cleanliness (for interview defensibility).

## Decision
We will use a **Persistent Worker Process (Standard I/O)** architecture.
1. The Node.js server will spawn the C++ executable once upon startup using `child_process.spawn()`.
2. The C++ engine will load the transit graph into memory and wait in an event loop for input.
3. Node.js will write queries (e.g., origin, destination, time) to the C++ process's `stdin`.
4. The C++ engine will compute the route and print the result as JSON to `stdout`.
5. Node.js will parse this `stdout` stream and return the response to the client.

## Alternatives Considered
- **Child Process per Request:** Rejected. Booting a new C++ process and parsing the timetable graph from disk on every HTTP request introduces unacceptable latency.
- **Node-API (Native Addon):** Rejected. While highly performant, compiling C++ directly into Node.js via `node-gyp` introduces a massive technology surface area that is difficult to defend in interviews (V8 internals, libuv). It also means a C++ segfault will crash the web server.
- **Standalone HTTP/gRPC Microservice:** Rejected. While architecturally sound, it requires adding third-party networking libraries to C++ (e.g., `cpp-httplib`) and managing network ports, which overcomplicates deployment for a single-node free-tier hosting environment.

## Consequences
- The C++ engine must be designed to run continuously without memory leaks.
- We must implement a robust framing protocol (e.g., newline-delimited JSON) over `stdin/stdout` to handle asynchronous queries reliably in Node.js.
- Deployment is simplified to a single machine/container containing both Node.js and the compiled C++ binary.
