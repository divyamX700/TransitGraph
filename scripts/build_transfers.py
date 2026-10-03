"""data/gtfs/transfers.txt: walking links between stations of different lines that are close enough
to change between on foot (a local station and its metro station, two metro lines at an interchange,
two local stations of different railway lines such as Prabhadevi and Parel).

For every pair of stops of different lines less than CANDIDATE_M apart in a straight line (two local
stations count only if no train runs between them, so neighbours on one line are not linked), the
real walking route is looked up (Valhalla pedestrian routing on OpenStreetMap). Pairs whose walk
is at most MAX_WALK_M become two directed footpaths. Walking time = routed walking time + ACCESS_MIN
(getting in and out of the two stations: entrances, stairs, ticket gates). Results are cached in
data/metro/walks.json so the build does not need the network again.

Run after compile_gtfs.py (it reads stops.txt).
"""
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request

from common import DATA, GTFS
from metro import haversine

WALKS_FILE = DATA / "metro" / "walks.json"
MANUAL_FILE = DATA / "metro" / "interchanges.json"
CANDIDATE_M = 1000
MAX_WALK_M = 1000
ACCESS_MIN = 2
VALHALLA = "https://valhalla1.openstreetmap.de/route?json="


def walk(a, b):
    """(metres, minutes) of the pedestrian route from a to b; a and b are (lat, lon)."""
    body = {"locations": [{"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}], "costing": "pedestrian", "units": "km"}
    request = urllib.request.Request(VALHALLA + urllib.parse.quote(json.dumps(body)),
                                     headers={"User-Agent": "transitgraph-data-pipeline/1.0"})
    for attempt in range(4):
        try:
            summary = json.load(urllib.request.urlopen(request, timeout=30))["trip"]["summary"]
            return round(summary["length"] * 1000), summary["time"] / 60
        except Exception as e:
            print(f"  valhalla: {str(e)[:60]}", file=sys.stderr)
            time.sleep(2 + attempt * 3)
    sys.exit("pedestrian routing unavailable")


def routes_serving():
    """stop id -> the set of route ids that call there"""
    with open(GTFS / "trips.txt", encoding="utf-8") as f:
        route_of = {r["trip_id"]: r["route_id"] for r in csv.DictReader(f)}
    served = {}
    with open(GTFS / "stop_times.txt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            served.setdefault(r["stop_id"], set()).add(route_of[r["trip_id"]])
    return served


def main():
    with open(GTFS / "stops.txt", encoding="utf-8") as f:
        stops = {r["stop_id"]: r for r in csv.DictReader(f)}
    coord = {s: (float(r["stop_lat"]), float(r["stop_lon"])) for s, r in stops.items()}
    line = {s: r.get("stop_line", "") or r["stop_id"] for s, r in stops.items()}  # local stops: one "line" each
    metro = [s for s, r in stops.items() if r.get("stop_mode") != "LOCAL"]

    cache = json.load(open(WALKS_FILE, encoding="utf-8")) if WALKS_FILE.exists() else {}
    pairs = set()
    for m in metro:
        for s in stops:
            if s != m and line[s] != line[m] and haversine(*coord[m], *coord[s]) < CANDIDATE_M:
                pairs.add(tuple(sorted((m, s))))
    served = routes_serving()
    local = sorted(s for s in stops if s not in metro)
    for i, a in enumerate(local):
        for b in local[i + 1:]:
            if not served[a] & served[b] and haversine(*coord[a], *coord[b]) < CANDIDATE_M:
                pairs.add((a, b))

    fresh = 0
    for a, b in sorted(pairs):
        key = f"{a}|{b}"
        if key not in cache:
            metres, minutes = walk(coord[a], coord[b])
            cache[key] = {"meters": metres, "walk_minutes": round(minutes, 1)}
            fresh += 1
            time.sleep(0.3)
    if fresh:
        with open(WALKS_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1, sort_keys=True)

    manual = {tuple(sorted((i["a"], i["b"]))): i for i in json.load(open(MANUAL_FILE, encoding="utf-8"))["interchanges"]}
    for pair, i in manual.items():
        assert pair in pairs, f"{pair} in interchanges.json is not a candidate pair"
        cache[f"{pair[0]}|{pair[1]}"] = {"meters": i["meters"], "walk_minutes": round(i["meters"] / 80, 1)}

    rows, kept = [], []
    for a, b in sorted(pairs):
        w = cache[f"{a}|{b}"]
        if w["meters"] > MAX_WALK_M and (a, b) not in manual:
            continue
        seconds = (math.ceil(w["walk_minutes"]) + ACCESS_MIN) * 60
        kept.append((a, b, w["meters"], seconds // 60))
        rows += [[a, b, 2, seconds, w["meters"]], [b, a, 2, seconds, w["meters"]]]
    with open(GTFS / "transfers.txt", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time", "distance_m"])
        w.writerows(rows)
    print(f"{len(pairs)} candidate pairs ({fresh} newly routed), {len(kept)} walkable within {MAX_WALK_M} m")
    for a, b, metres, minutes in kept:
        print(f"  {stops[a]['stop_name']} ({line[a]}) <-> {stops[b]['stop_name']} ({line[b]}): {metres} m, {minutes} min")


if __name__ == "__main__":
    main()
