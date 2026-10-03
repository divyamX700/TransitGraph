"""Checks the routing engine against what a correct router must do, using a deliberately simple
reference written from the definition rather than from the engine's algorithm.

For random and hand-picked queries it asserts that
  1. every journey the engine returns is real: each vehicle leg is a trip from the timetable that
     boards and alights at stops in order at the printed times; each walking leg is a footpath
     from transfers.txt; legs connect (5 minutes to change vehicles, none after a walk); the first
     leg leaves no earlier than requested;
  2. the set of journeys is the Pareto front: for every number of vehicles k (0 = walking all the way)
     the engine reports a journey exactly when k vehicles can reach the target earlier than any fewer can,
     with the earliest possible arrival (walking between stops is free of "vehicles");
  3. bad input is answered with an error and never kills the engine.

    python tests/check_engine.py [path/to/engine] [--n 400] [--seed 1]
Exit code 1 on any failure.
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "data" / "gtfs"
TRANSFER_MINUTES = 5   # changing from one vehicle to another
MAX_VEHICLES = 6       # the engine's round limit
DAY = 1440


def minutes(t):
    return int(t[:2]) * 60 + int(t[3:5])


def read(name):
    with open(GTFS / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_network():
    """trips: id -> (shape, line, [(stop, arrival, departure)]), each also shifted a day as
    '<id>_nextday' (the engine plans over a 48-hour window); walks: stop -> {stop: (minutes, metres)};
    modes: line -> METRO / LOCAL / MONORAIL."""
    route_type = {r["route_id"]: r["route_type"] for r in read("routes.txt")}
    modes = {l: {"1": "METRO", "12": "MONORAIL"}.get(t, "LOCAL") for l, t in route_type.items()}
    meta = {r["trip_id"]: (r["shape_id"], r["route_id"]) for r in read("trips.txt")}
    rows = defaultdict(list)
    for r in read("stop_times.txt"):
        rows[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"], minutes(r["arrival_time"]),
                                   minutes(r["departure_time"])))
    trips = {}
    for tid, seq in rows.items():
        seq = [x[1:] for x in sorted(seq)]
        shape, line = meta[tid]
        trips[tid] = (shape, line, seq)
        trips[tid + "_nextday"] = (shape, line, [(s, a + DAY, d + DAY) for s, a, d in seq])
    walks = defaultdict(dict)
    if (GTFS / "transfers.txt").exists():
        for r in read("transfers.txt"):
            walks[r["from_stop_id"]][r["to_stop_id"]] = (math.ceil(int(r["min_transfer_time"]) / 60), int(r["distance_m"]))
    return trips, walks, modes


def reference_front(trips, walks, src, dst, t0):
    """[(vehicles, arrival)] for every vehicle count that beats all smaller counts.
    by_vehicle[s]: earliest arrival at s on a vehicle; on_foot[s]: earliest arrival at s on foot (the
    origin counts as arriving on foot at t0). A vehicle may be boarded once the passenger is there:
    immediately after walking, 5 minutes after leaving another vehicle. One walk may follow a vehicle
    leg (and one may start the journey)."""
    INF = 10**9
    by_vehicle = {}
    on_foot = {src: t0}
    for q, (walk_min, _) in walks.get(src, {}).items():
        on_foot[q] = min(on_foot.get(q, INF), t0 + walk_min)
    front = []
    best_dst = INF
    if dst != src and dst in on_foot:  # walking all the way, no vehicle at all
        front.append((0, on_foot[dst]))
        best_dst = on_foot[dst]
    for k in range(1, MAX_VEHICLES + 1):
        new_vehicle = dict(by_vehicle)
        for _, _, seq in trips.values():
            if seq[-1][2] < t0:  # finished before the passenger can be there
                continue
            riding = False
            for stop, arrival, departure in seq:
                if riding and arrival < new_vehicle.get(stop, INF):
                    new_vehicle[stop] = arrival
                if not riding:
                    ready = min(on_foot.get(stop, INF), by_vehicle.get(stop, INF - TRANSFER_MINUTES) + TRANSFER_MINUTES)
                    riding = ready < INF and departure >= ready
        new_foot = dict(on_foot)
        for s, arrival in new_vehicle.items():
            for q, (walk_min, _) in walks.get(s, {}).items():
                if arrival + walk_min < new_foot.get(q, INF):
                    new_foot[q] = arrival + walk_min
        arrive = min(new_vehicle.get(dst, INF), new_foot.get(dst, INF))
        if arrive < best_dst:
            front.append((k, arrive))
            best_dst = arrive
        by_vehicle, on_foot = new_vehicle, new_foot
    return front


class Engine:
    def __init__(self, path):
        self.p = subprocess.Popen([path, str(GTFS)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        assert self.p.stdout.readline().strip() == "READY"
        self.n = 0

    def ask(self, src, dst, t):
        self.n += 1
        tag = f"q{self.n}"
        self.p.stdin.write(f"{tag}|{src},{dst},{t}\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        assert line, "engine died"
        got_tag, payload = line.rstrip("\n").split("|", 1)
        assert got_tag == tag, f"answered {got_tag} to {tag}"
        return json.loads(payload)

    def alive(self):
        return self.p.poll() is None


def validate_journey(net, journey, src, dst, t0):
    trips, walks, modes = net
    errs = []
    if journey[0]["from"] != src or journey[-1]["to"] != dst:
        errs.append("does not run from the origin to the target")
    if journey[0]["dep_min"] < t0:
        errs.append(f"leaves at {journey[0]['dep']} before the requested time")
    prev = None
    for leg in journey:
        if leg["is_walk"]:
            walk = walks.get(leg["from"], {}).get(leg["to"])
            if walk is None:
                errs.append(f"no footpath {leg['from']} -> {leg['to']}")
            elif (leg["arr_min"] - leg["dep_min"], leg["walk_m"]) != walk:
                errs.append(f"walk {leg['from']}->{leg['to']}: engine says {leg['arr_min'] - leg['dep_min']} min / "
                            f"{leg['walk_m']} m, transfers.txt says {walk}")
            if leg["mode"] != "WALK" or leg["trip_id"]:
                errs.append("walking leg mislabelled")
            if prev is not None and prev["is_walk"]:
                errs.append("two walks in a row")
        else:
            trip = trips.get(leg["trip_id"])
            if trip is None:
                errs.append(f"unknown trip {leg['trip_id']}")
                prev = leg
                continue
            shape, line, seq = trip
            stops = [s for s, _, _ in seq]
            if leg["route_id"] != shape or leg["line"] != line or leg["mode"] != modes[line]:
                errs.append(f"trip {leg['trip_id']} labelled {leg['route_id']}/{leg['line']}/{leg['mode']}, "
                            f"timetable says {shape}/{line}/{modes[line]}")
            if leg["from"] not in stops or leg["to"] not in stops or stops.index(leg["from"]) >= stops.index(leg["to"]):
                errs.append(f"trip {leg['trip_id']} does not go {leg['from']} -> {leg['to']} in that order")
                prev = leg
                continue
            dep = seq[stops.index(leg["from"])][2]
            arr = seq[stops.index(leg["to"])][1]
            if (leg["dep_min"], leg["arr_min"]) != (dep, arr):
                errs.append(f"trip {leg['trip_id']} {leg['from']}->{leg['to']}: engine says "
                            f"{leg['dep_min']}-{leg['arr_min']}, timetable {dep}-{arr}")
        if prev is not None:
            if prev["to"] != leg["from"]:
                errs.append(f"legs do not connect: {prev['to']} then {leg['from']}")
            need = TRANSFER_MINUTES if not prev["is_walk"] and not leg["is_walk"] else 0
            if leg["dep_min"] < prev["arr_min"] + need:
                errs.append(f"only {leg['dep_min'] - prev['arr_min']} min between legs at {leg['from']} (need {need})")
        prev = leg
    return errs


def check_query(engine, net, src, dst, t0, failures):
    answer = engine.ask(src, dst, t0)
    label = f"{src} -> {dst} at {t0 // 60:02d}:{t0 % 60:02d}"
    if "routes" not in answer:
        failures.append(f"{label}: error answer {answer}")
        return
    journeys = answer["routes"]
    for j in journeys:
        for e in validate_journey(net, j, src, dst, t0):
            failures.append(f"{label}: {e}")
    got = [(sum(not l["is_walk"] for l in j), j[-1]["arr_min"]) for j in journeys]
    want = reference_front(net[0], net[1], src, dst, t0) if src != dst else []
    if got != want:
        failures.append(f"{label}: engine front {got}, correct front {want}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("engine", nargs="?", default=str(ROOT / "engine" / ("raptor.exe" if os.name == "nt" else "raptor")))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    net = load_network()
    stops = [r["stop_id"] for r in read("stops.txt")]
    engine = Engine(args.engine)
    failures = []

    # hand-picked cases: long lines, branches, through services, interchanges, midnight edges
    named = [("CHURCHGATE", "VIRAR", 480), ("CHURCHGATE", "DAHANU_ROAD", 300), ("CSMT", "KASARA", 1000),
             ("CSMT", "KHOPOLI", 1100), ("KALYAN", "CSMT", 480), ("PANVEL", "GOREGAON", 330),
             ("GOREGAON", "PANVEL", 720), ("CHURCHGATE", "URAN", 600), ("THANE", "PANVEL", 600),
             ("VASHI", "THANE", 1380), ("CHURCHGATE", "KALYAN", 1430), ("CSMT", "CHURCHGATE", 1439),
             ("VIRAR", "CSMT", 0), ("DAHANU_ROAD", "CHURCHGATE", 1200), ("ANDHERI", "GHATKOPAR", 540),
             ("DADAR", "DADAR", 600), ("KANDIVALI", "BHAYANDAR", 600), ("URAN", "CSMT", 700)]
    named += [q for q in [
        ("M1_VERSOVA", "M1_GHATKOPAR", 480), ("M1_GHATKOPAR", "M1_VERSOVA", 1400), ("M3_CUFFE_PARADE", "M3_AAREY_JVLR", 600),
        ("M3_CHURCHGATE", "M3_DADAR", 700), ("M7_KASHIGAON", "M7_GUNDAVALI", 500), ("M2A_DAHISAR_EAST", "M2A_ANDHERI_WEST", 540),
        ("M2A_DAHISAR_EAST", "M7_KASHIGAON", 540), ("M2A_ANDHERI_WEST", "M7_GUNDAVALI", 600),
        ("CHURCHGATE", "M1_GHATKOPAR", 600), ("M1_VERSOVA", "CSMT", 600), ("ANDHERI", "M3_CHURCHGATE", 600),
        ("M3_AAREY_JVLR", "VIRAR", 600), ("JOGESHWARI", "M7_KASHIGAON", 600),
        ("MANKHURD", "M2B_MANDALE", 540), ("M2B_DIAMOND_GARDEN", "DADAR", 540), ("GHATKOPAR", "M3_DADAR", 600),
        ("M1_ANDHERI", "ANDHERI", 600), ("DAHISAR", "M7_KASHIGAON", 600)] if q[0] in stops and q[1] in stops]
    for q in named:
        check_query(engine, net, *q, failures)

    rnd = random.Random(args.seed)
    for _ in range(args.n):
        a, b = rnd.sample(stops, 2)
        check_query(engine, net, a, b, rnd.randrange(0, DAY), failures)

    # unreachable / invalid input: an answer, not a crash
    if engine.ask("CHURCHGATE", "NO_SUCH_STOP", 600).get("routes") != []:
        failures.append("unknown stop should give no routes")
    if engine.ask("CHURCHGATE", "CHURCHGATE", 600).get("routes") != []:
        failures.append("same origin and target should give no routes")
    for bad in ("abc", "", "-5", "1440", "99999999999999999999", "12.5", "6 00"):
        engine.p.stdin.write(f"b|CHURCHGATE,VIRAR,{bad}\n")
        engine.p.stdin.flush()
        line = engine.p.stdout.readline()
        if not line.startswith("b|") or "error" not in line:
            failures.append(f"time {bad!r} should be rejected, got {line!r}")
    for bad_line in ("no pipe at all", "x|CHURCHGATE", "x|,,", "|||", "x|A,B,C,D"):
        engine.p.stdin.write(bad_line + "\n")
        engine.p.stdin.flush()
        engine.p.stdout.readline()
    if not engine.alive():
        failures.append("engine died on invalid input")
    elif engine.ask("CHURCHGATE", "VIRAR", 480).get("routes") is None:
        failures.append("engine stopped answering after invalid input")

    print(f"{len(named) + args.n} queries, {len(failures)} failures")
    for f in failures[:40]:
        print("  FAIL", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
