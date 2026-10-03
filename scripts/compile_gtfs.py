"""data/extracted/*.csv + data/station_mapping.json -> data/gtfs (everything except shapes.txt,
which generate_shapes_kml.py builds from the trips written here).

A train number can appear in several timetables: a through service is listed on every line it
touches, each showing only its own part. Pieces of one train are therefore assembled here
rather than deduplicated by number.
"""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict

import metro
from common import EXTRACTED, GTFS, STATION_MAPPING

# Highest priority first. Specialist timetables (Dahanu Road, Trans-Harbour, Port) list a
# train's full run; the main-line timetables only show the part on their own line.
SOURCES = ["western_dahanu", "trans_harbour", "port_line", "harbour_dn", "harbour_up",
           "central_dn", "central_up", "western_dn", "western_up"]

# Route family from the timetable a train came from; stops unique to a branch override it
# (the Harbour timetables also list the Thane-Vashi/Panvel trains, for example).
DEFAULT_ROUTE = {"central": "CR_MAIN", "harbour": "CR_HARBOUR", "western": "WR_MAIN",
                 "port": "CR_PORT", "trans": "CR_TRANS"}
BRANCH_STOPS = [
    ("CR_PORT", {"TARGHAR", "BAMANDONGRI", "KHARKOPAR", "GAVHAN", "SHEMATIKHAR", "NHAVE_SHEVA",
                 "DRONAGIRI", "URAN"}),
    ("CR_TRANS", {"DIGHA_GAON", "AIROLI", "RABALE", "GHANSOLI", "KOPAR_KHAIRANE", "TURBHE"}),
    ("WR_DAHANU", {"VAITERNA", "SAPHALE", "KELVE_ROAD", "PALGHAR", "UMROLI", "BOISAR", "VANGAON",
                   "DAHANU_ROAD"}),
]
# The timetables call it "CSMT"; riders see the full name, the same one the metro station has
DISPLAY_NAMES = {"CSMT": "Chhatrapati Shivaji Maharaj Terminus"}

ROUTES = [  # id, agency, name, display colour
    ("CR_MAIN", "CR", "Central Line", "#DC2626"), ("CR_HARBOUR", "CR", "Harbour Line", "#0891B2"),
    ("CR_TRANS", "CR", "Trans-Harbour Line", "#7C3AED"), ("CR_PORT", "CR", "Port Line", "#059669"),
    ("WR_MAIN", "WR", "Western Line", "#2563EB"), ("WR_DAHANU", "WR", "Western Dahanu Line", "#2563EB"),
]


def write_csv(name, header, rows):
    with open(GTFS / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def norm(name):
    return " ".join(name.split()).casefold()


def load_stations():
    mapping = json.load(open(STATION_MAPPING, encoding="utf-8"))
    ids, alias = {}, {}
    for name, s in mapping.items():
        ids[name] = name.replace(" ", "_").upper()
        for raw in [name, *s["raw_names"]]:
            if alias.setdefault(norm(raw), name) != name:
                sys.exit(f"alias {raw!r} maps to both {alias[norm(raw)]!r} and {name!r}")
    for route, stops in BRANCH_STOPS:
        missing = stops - set(ids.values())
        if missing:
            sys.exit(f"{route} branch stops not in the station mapping: {sorted(missing)}")
    return mapping, ids, alias


def read_pieces(alias, ids):
    """pieces[train] = [(source, [(stop_id, minute_of_day), ...]), ...] in source priority order.
    A stop repeating inside one source's rows starts a new run: a train can't call at a
    station twice, so the rows belong to two separate services sharing a number."""
    pieces, unresolved, typos = defaultdict(list), set(), []
    for source in SOURCES:
        rows = defaultdict(list)
        with open(EXTRACTED / f"{source}.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = alias.get(norm(r["station"]))
                if name is None:
                    unresolved.add(r["station"])
                    continue
                h, m = map(int, r["time"].split(":"))
                rows[r["train_number"]].append((ids[name], h * 60 + m))
        for train, seq in rows.items():
            run, seen = [], set()
            for stop, t in seq:
                if stop in seen:
                    pieces[train].append((source, run))
                    run, seen = [], set()
                run.append((stop, t))
                seen.add(stop)
            pieces[train].append((source, run))
            for stop_a, stop_b in out_of_order(run):
                typos.append(f"{train} ({source}): {stop_a} -> {stop_b}")
    if unresolved:
        sys.exit(f"station names missing from {STATION_MAPPING.name}: {sorted(unresolved)}")
    return pieces, typos


def out_of_order(run):
    """Consecutive stations (in the timetable's own row order) whose times go backwards:
    a typo in the source. Compiling still sorts by time, so the trip stays usable."""
    times = past_midnight([t for _, t in run])
    return [(run[i][0], run[i + 1][0]) for i in range(len(run) - 1) if times[i + 1] < times[i]]


def assemble(train, train_pieces, stats):
    """One train number -> list of trips; each trip is {stop_id: [arrival, departure]}."""
    trips, trip_source = [], []
    for source, run in train_pieces:
        stops = {s for s, _ in run}
        others = [i for i, src in enumerate(trip_source) if src != source]
        overlaps = [(len(stops & trips[i].keys()), i) for i in others]
        best, target = max(overlaps, default=(0, None))
        if best >= 2:
            # Same run recorded in a second timetable: keep the higher-priority one.
            if any(abs(t - trips[target][s][0]) > 1 for s, t in run if s in trips[target]):
                stats["duplicate pieces with differing times"] += 1
            stats["duplicate pieces dropped"] += 1
        elif len(run) < 2:
            stats["single-stop fragments dropped"] += 1
        elif best == 1:
            # Through service: this part starts where the other ends (they share one stop).
            for s, t in run:
                if s in trips[target]:
                    trips[target][s] = [min(trips[target][s][0], t), max(trips[target][s][1], t)]
                else:
                    trips[target][s] = [t, t]
            stats["through services joined"] += 1
        else:
            if trips:
                stats["extra runs under a shared train number"] += 1
            trips.append({s: [t, t] for s, t in run})
            trip_source.append(source)
    return [(t, trip_source[i]) for i, t in enumerate(trips) if len(t) >= 2]


def past_midnight(times):
    """A run spanning 18+ hours of clock time crosses midnight: its early-morning times
    belong to the next day (24:xx)."""
    crosses = max(times) // 60 - min(times) // 60 >= 18
    return [t + 1440 if crosses and t < 12 * 60 else t for t in times]


def chronological(trip):
    """Stops in time order as [(stop, arrival, departure)]."""
    stops = list(trip)
    flat = past_midnight([t for s in stops for t in trip[s]])
    return sorted(((s, flat[2 * i], flat[2 * i + 1]) for i, s in enumerate(stops)),
                  key=lambda x: (x[1], x[2]))


def hhmmss(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def route_of(stops, source):
    for route, branch in BRANCH_STOPS:
        if branch & stops:
            return route
    return DEFAULT_ROUTE[source.split("_")[0]]


def main():
    GTFS.mkdir(exist_ok=True)
    mapping, ids, alias = load_stations()
    pieces, typos = read_pieces(alias, ids)

    lines = metro.build()
    write_csv("agency.txt", ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang"],
              [["CR", "Central Railway", "https://cr.indianrailways.gov.in/", "Asia/Kolkata", "en"],
               ["WR", "Western Railway", "https://wr.indianrailways.gov.in/", "Asia/Kolkata", "en"],
               *lines["agencies"]])
    write_csv("routes.txt", ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color"],
              [[r, a, r, n, 2, c] for r, a, n, c in ROUTES] + lines["routes"])
    write_csv("calendar.txt", ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
                               "saturday", "sunday", "start_date", "end_date"],
              [["weekday", 1, 1, 1, 1, 1, 1, 0, 20240101, 20261231]])
    write_csv("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_mode", "stop_line"],
              [[ids[n], DISPLAY_NAMES.get(n, n), s["lat"], s["lon"], "LOCAL", ""] for n, s in mapping.items()] + lines["stops"])

    stats, trips_rows, stop_times_rows, per_route = Counter(), [], [], Counter()
    for train in sorted(pieces):
        for k, (trip, source) in enumerate(assemble(train, pieces[train], stats)):
            seq = chronological(trip)
            stop_ids = [s for s, _, _ in seq]
            route = route_of(set(stop_ids), source)
            trip_id = train if k == 0 else f"{train}-{k + 1}"
            shape_hash = hashlib.md5("_".join(stop_ids).encode()).hexdigest()[:4]
            shape_id = f"SHP_{route}_{stop_ids[0]}_TO_{stop_ids[-1]}_{shape_hash}"
            direction = {"up": 0, "dn": 1}.get(source[-2:], "")
            trips_rows.append([route, "weekday", trip_id, direction, shape_id])
            stop_times_rows += [[trip_id, hhmmss(a), hhmmss(d), s, i + 1] for i, (s, a, d) in enumerate(seq)]
            per_route[route] += 1
    local_trips = len(trips_rows)
    trips_rows += lines["trips"]
    stop_times_rows += lines["stop_times"]
    write_csv("trips.txt", ["route_id", "service_id", "trip_id", "direction_id", "shape_id"], trips_rows)
    write_csv("stop_times.txt", ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
              stop_times_rows)

    unused = set(ids.values()) - {r[3] for r in stop_times_rows}
    print(f"{len(trips_rows)} trips ({local_trips} local, {len(lines['trips'])} metro), "
          f"{len(stop_times_rows)} stop times, {len(ids)} local + {len(lines['stops'])} metro stops")
    print("trips per route:", dict(per_route))
    for what, n in stats.items():
        print(f"  {what}: {n}")
    if typos:
        print(f"WARNING: {len(typos)} timetable entries run backwards in time (probable typos in the "
              "source PTT; check against the PDF):")
        print("  " + "\n  ".join(typos))
    if unused:
        print(f"WARNING: stops no trip serves: {sorted(unused)}")


if __name__ == "__main__":
    main()
