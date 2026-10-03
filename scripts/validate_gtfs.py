"""Checks data/gtfs against facts about the Mumbai suburban network, not against how the
compile scripts happen to behave: every expectation below is written out independently
(station order along each line, which stations belong to which line, plausible speeds).

Run after rebuilding the data:  python scripts/validate_gtfs.py   (exit code 1 on any failure)
"""
import csv
import sys
from collections import defaultdict

from common import GTFS
from generate_shapes_kml import build_track_graph, haversine

# Timetable entries known to be wrong in the source PTT (the PTT itself has the typo).
KNOWN_SOURCE_TYPOS = {
    "90280": "Mira Road 09:26 should be about 09:16 (listed after Dahisar 09:23)",
    "90981": "Goregaon->Malad 1 min and Andheri->Jogeshwari 7 min are implausible",
}
# Trains whose timetable cannot be ingested.
KNOWN_MISSING_TRAINS = {
    "93003", "93024", "93027", "93032", "93037", "93042",  # Virar->Dahanu Road: only the Virar time is printed
    "90909", "90911", "94095",  # whole run printed in one merged Excel cell
}

# Stations in order along each trunk line. Trips must visit the stations of a trunk in this order.
WESTERN = ["CHURCHGATE", "MARINE_LINES", "CHARNI_ROAD", "GRANT_ROAD", "MUMBAI_CENTRAL", "MAHALAXMI",
           "LOWER_PAREL", "PRABHADEVI", "DADAR", "MATUNGA_ROAD", "MAHIM", "BANDRA", "KHAR_ROAD",
           "SANTACRUZ", "VILE_PARLE", "ANDHERI", "JOGESHWARI", "RAM_MANDIR", "GOREGAON", "MALAD",
           "KANDIVALI", "BORIVALI", "DAHISAR", "MIRA_ROAD", "BHAYANDAR", "NAIGAON", "VASAI_ROAD",
           "NALLA_SOPARA", "VIRAR", "VAITERNA", "SAPHALE", "KELVE_ROAD", "PALGHAR", "UMROLI", "BOISAR",
           "VANGAON", "DAHANU_ROAD"]
CENTRAL = ["CSMT", "MASJID", "SANDHURST_ROAD", "BYCULLA", "CHINCHPOKLI", "CURREY_ROAD", "PAREL", "DADAR",
           "MATUNGA", "SION", "KURLA", "VIDYAVIHAR", "GHATKOPAR", "VIKHROLI", "KANJUR_MARG", "BHANDUP",
           "NAHUR", "MULUND", "THANE", "KALVA", "MUMBRA", "DIVA", "KOPAR", "DOMBIVLI", "THAKURLI", "KALYAN"]
HARBOUR = ["CSMT", "MASJID", "SANDHURST_ROAD", "DOCKYARD_ROAD", "REAY_ROAD", "COTTON_GREEN", "SEWRI",
           "VADALA_ROAD", "GURU_TEGH_BAHADUR_NAGAR", "CHUNABHATTI", "KURLA", "TILAKNAGAR", "CHEMBUR",
           "GOVANDI", "MANKHURD", "VASHI", "SANPADA", "JUINAGAR", "NERUL", "SEAWOODS_DARAVE", "CBD_BELAPUR",
           "KHARGHAR", "MANSAROVAR", "KHANDESHWAR", "PANVEL"]
# Stations only one railway serves, to catch trips filed under the wrong line.
WESTERN_ONLY = {"CHURCHGATE", "MARINE_LINES", "MUMBAI_CENTRAL", "BORIVALI", "VIRAR", "BHAYANDAR", "DAHISAR"}
CENTRAL_ONLY = {"MASJID", "BYCULLA", "GHATKOPAR", "THANE", "KALYAN", "DOMBIVLI", "KARJAT", "KASARA"}
# A trip serving one of these stations can only belong to that line.
STATION_TO_ROUTE = {"URAN": "CR_PORT", "AIROLI": "CR_TRANS", "DIGHA_GAON": "CR_TRANS",
                    "DAHANU_ROAD": "WR_DAHANU", "PALGHAR": "WR_DAHANU"}

MAX_SPEED_KMH = 120       # no suburban train does more between two timetable points
MAX_TRIP_MINUTES = 330    # longest run (Churchgate-Dahanu Road) is under 3 hours; Kasara/Khopoli-CSMT ~3h
MIN_STOP_SEPARATION_M = 200
SHAPE_END_TOLERANCE_M = 1500


METRO_LINES = {"M1", "M2A", "M2B", "M3", "M7"}
# Facts about each active metro line: station count, key stations in order (substring match on the
# name), end-to-end minutes (None = no published figure), published route length in km, first and last
# departure from each terminal (official timetables), and the published peak headway in minutes
# together with a time inside the peak at which to measure it.
METRO_FACTS = {
    "M1": dict(stations=12, order=["Versova", "D. N. Nagar", "Azad Nagar", "Andheri", "Western Express Highway", "Chakala",
                                   "Airport Road", "Marol Naka", "Saki Naka", "Asalpha", "Jagruti Nagar", "Ghatkopar"],
               minutes=21, km=11.4, departures={0: ("05:30", "23:25"), 1: ("05:30", "23:50")}, peak=(3.5, "08:30")),
    "M2A": dict(stations=17, order=["Dahisar", "Anand Nagar", "Borivali", "Kandivali", "Malad", "Goregaon", "Oshiwara", "Andheri"],
                minutes=40, km=18.6, departures={0: ("06:00", "22:35"), 1: ("05:55", "23:00")}, peak=(6, "08:30")),
    "M3": dict(stations=27, order=["Aarey", "SEEPZ", "Marol Naka", "Santacruz", "Bandra Kurla", "Dharavi", "Dadar", "Worli", "Mahalaxmi",
                                   "Grant Road", "Chhatrapati Shivaji Maharaj Terminus", "Churchgate", "Cuffe Parade"],
               minutes=54, km=33.5, departures={0: ("05:55", "22:30"), 1: ("05:55", "22:30")}, peak=(3.5, "09:00")),
    "M7": dict(stations=17, order=["Gundavali", "Mogra", "Jogeshwari", "Goregaon", "Aarey", "Dindoshi", "Magathane", "Dahisar",
                                   "Pandurang Wadi", "Miragaon", "Kashigaon"],
               minutes=None, km=21.5, departures={0: ("06:00", "23:00"), 1: ("05:50", "22:30")}, peak=(7.5, "08:30")),
    "M2B": dict(stations=5, order=["Diamond Garden", "Shivaji Chowk", "BSNL Metro", "Mankhurd", "Mandale"],
                minutes=None, km=5.4, departures={0: ("06:00", "22:30"), 1: ("06:00", "22:15")}, peak=(9.5, "09:00")),
}
# (stop, stop) pairs that are real interchanges between a metro station and a local or other metro station
INTERCHANGES = [("M1_ANDHERI", "ANDHERI"), ("M1_GHATKOPAR", "GHATKOPAR"), ("M3_CHURCHGATE", "CHURCHGATE"),
                ("M3_CHHATRAPATI_SHIVAJI_MAHARAJ_TERMINUS", "CSMT"), ("M3_GRANT_ROAD", "GRANT_ROAD"),
                ("M3_DADAR", "DADAR"), ("M3_MAHALAXMI", "MAHALAXMI"), ("M2B_MANKHURD", "MANKHURD"), ("M7_JOGESHWARI_EAST", "JOGESHWARI"), ("M3_SANTACRUZ", "SANTACRUZ"),
                ("M3_JAGANNATH_SHANKAR_SHETH_METRO", "MUMBAI_CENTRAL"), ("M1_MAROL_NAKA", "M3_MAROL_NAKA"),
                ("M1_D_N_NAGAR", "M2A_ANDHERI_WEST"), ("M1_WESTERN_EXPRESS_HIGHWAY", "M7_GUNDAVALI"),
                ("M2A_DAHISAR_EAST", "M7_DAHISAR_EAST"),
                ("PRABHADEVI", "PAREL"), ("CURREY_ROAD", "LOWER_PAREL")]  # Western and Central stations a short walk apart
MAX_FOOTPATH_M = 1200  # 1 km cap, except official interchanges listed in data/metro/interchanges.json


def to_minutes(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def check_metro(fail, stops, coord, trips, times, shapes, transfers):
    """Metro lines against their published facts, and the footpaths against known interchanges."""
    def f(msg):
        fail("metro", msg)

    by_line = defaultdict(list)
    for s, r in stops.items():
        if r["stop_line"] in METRO_FACTS:
            by_line[r["stop_line"]].append(s)
    for line, facts in METRO_FACTS.items():
        sids = by_line.get(line, [])
        if len(sids) != facts["stations"]:
            f(f"{line}: {len(sids)} stations, expected {facts['stations']}")
        line_trips = {d: sorted(t for t, r in trips.items() if r["route_id"] == line and r["direction_id"] == str(d))
                      for d in (0, 1)}
        if not line_trips[0] or not line_trips[1]:
            f(f"{line}: no trips in one direction")
            continue
        names = [stops[s]["stop_name"] for _, s, _, _ in times[line_trips[0][0]]]
        position = -1
        for key in facts["order"]:
            hit = [i for i, n in enumerate(names) if key.lower() in n.lower()]
            if not hit or hit[0] <= position:
                f(f"{line}: station {key!r} missing or out of order in {names}")
                break
            position = hit[0]
        for d, (first, last) in facts["departures"].items():
            deps = sorted(times[t][0][3] for t in line_trips[d])
            if deps[0] != to_minutes(first) or deps[-1] != to_minutes(last):
                f(f"{line} direction {d}: departures {deps[0]}..{deps[-1]} min, published {first}-{last}")
            gaps = [b - a for a, b in zip(deps, deps[1:])]
            if max(gaps) > 15:
                f(f"{line} direction {d}: a gap of {max(gaps)} min between trains")
            peak, at = facts["peak"]
            around = [g for dep, g in zip(deps, gaps) if to_minutes(at) <= dep < to_minutes(at) + 60]
            if around and abs(sum(around) / len(around) - peak) > 0.6:
                f(f"{line} direction {d}: headway around {at} is {sum(around) / len(around):.1f} min, published {peak}")
        trip = times[line_trips[0][0]]
        duration = trip[-1][2] - trip[0][3]
        if facts["minutes"] and abs(duration - facts["minutes"]) > 1:
            f(f"{line}: end to end {duration} min, published {facts['minutes']}")
        pts = [(la, lo) for _, la, lo in sorted(shapes.get(trips[line_trips[0][0]]["shape_id"], []))]
        length = sum(haversine(*a, *b) for a, b in zip(pts, pts[1:])) / 1000
        # published lengths include track beyond the terminal stations, so the shape may be somewhat shorter
        if not 0.8 * facts["km"] <= length <= 1.15 * facts["km"]:
            f(f"{line}: track shape is {length:.1f} km, published {facts['km']} km")
        for (_, s1, _, d1), (_, s2, a2, _) in zip(trip, trip[1:]):
            km = haversine(*coord[s1], *coord[s2]) / 1000
            if a2 - d1 < 1 or (km > 0.5 and km / ((a2 - d1) / 60) > 90):
                f(f"{line}: {s1}->{s2} is {km:.1f} km in {a2 - d1} min")
    known = {(r["from_stop_id"], r["to_stop_id"]): r for r in transfers}
    for (a, b), r in known.items():
        if (b, a) not in known or known[(b, a)]["min_transfer_time"] != r["min_transfer_time"]:
            f(f"footpath {a}->{b} has no matching reverse")
        metres, minutes = int(r["distance_m"]), int(r["min_transfer_time"]) / 60
        if metres > MAX_FOOTPATH_M:
            f(f"footpath {a}->{b} is {metres} m")
        if minutes < metres / 100 or minutes > metres / 50 + 6:  # 3-6 km/h plus time to get in and out
            f(f"footpath {a}->{b}: {minutes:.0f} min for {metres} m")
        if stops[a]["stop_line"] and stops[a]["stop_line"] == stops[b]["stop_line"]:
            f(f"footpath {a}->{b} joins two stations of the same line")
    for a, b in INTERCHANGES:
        if a in stops and b in stops and (a, b) not in known:
            f(f"interchange {a} <-> {b} has no footpath")


def read(name):
    with open(GTFS / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def minutes(t):
    h, m, _ = map(int, t.split(":"))
    return h * 60 + m


def main():
    stops = {r["stop_id"]: r for r in read("stops.txt")}
    coord = {s: (float(r["stop_lat"]), float(r["stop_lon"])) for s, r in stops.items()}
    trips = {r["trip_id"]: r for r in read("trips.txt")}
    routes = {r["route_id"] for r in read("routes.txt")}
    times = defaultdict(list)
    for r in read("stop_times.txt"):
        times[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"], minutes(r["arrival_time"]),
                                    minutes(r["departure_time"])))
    for seq in times.values():
        seq.sort()
    errors = defaultdict(list)

    def fail(check, msg):
        errors[check].append(msg)

    # --- references
    for t, r in trips.items():
        if r["route_id"] not in routes:
            fail("references", f"trip {t}: unknown route {r['route_id']}")
        if t not in times:
            fail("references", f"trip {t} has no stop times")
    for t in times:
        if t not in trips:
            fail("references", f"stop times for unknown trip {t}")
    used = {s for seq in times.values() for _, s, _, _ in seq}
    for s in stops:
        if s not in used:
            fail("references", f"stop {s} is served by no trip")
    for t, seq in times.items():
        for _, s, _, _ in seq:
            if s not in stops:
                fail("references", f"trip {t} visits unknown stop {s}")
    for r in routes:
        if not any(x["route_id"] == r for x in trips.values()):
            fail("references", f"route {r} has no trips")

    # --- stations
    local = {s: r for s, r in stops.items() if r["stop_mode"] == "LOCAL"}
    names = [r["stop_name"].casefold().replace(" ", "") for r in local.values()]
    for n in set(names):
        if names.count(n) > 1:
            fail("stations", f"station name appears twice: {n}")
    ids = sorted(local)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = haversine(*coord[a], *coord[b])
            if d < MIN_STOP_SEPARATION_M:
                fail("stations", f"{a} and {b} are only {d:.0f} m apart (one station under two names, or a bad coordinate)")
    for a in stops:
        if not (18.7 < coord[a][0] < 20.1 and 72.7 < coord[a][1] < 73.6):
            fail("stations", f"{a} is outside the Mumbai region: {coord[a]}")
    for line, order, tol in (("Western", WESTERN, 0.003), ("Central", CENTRAL, 0.012)):
        lats = [coord[s][0] for s in order]
        for a, b, la, lb in zip(order, order[1:], lats, lats[1:]):
            if lb < la - tol:  # both lines run north from the city
                fail("stations", f"{line} line: {b} ({lb:.4f}) lies south of {a} ({la:.4f})")

    # --- trips
    for t, seq in times.items():
        if t in KNOWN_SOURCE_TYPOS:
            continue
        stop_ids = [s for _, s, _, _ in seq]
        if len(stop_ids) < 2:
            fail("trips", f"trip {t} has fewer than 2 stops")
        if len(set(stop_ids)) != len(stop_ids):
            fail("trips", f"trip {t} visits a stop twice")
        for (_, s1, a1, d1), (_, s2, a2, d2) in zip(seq, seq[1:]):
            if a1 > d1 or d1 > a2 or a2 > d2:
                fail("trips", f"trip {t}: times go backwards at {s1}->{s2}")
                continue
            km = haversine(*coord[s1], *coord[s2]) / 1000
            if a2 > d1 and km / ((a2 - d1) / 60) > MAX_SPEED_KMH and km > 1.5:
                fail("trips", f"trip {t}: {s1}->{s2} is {km:.1f} km in {a2 - d1} min")
            if a2 == d1 and km > 1.5:
                fail("trips", f"trip {t}: {s1}->{s2} is {km:.1f} km in 0 min")
        if seq[-1][2] - seq[0][2] > MAX_TRIP_MINUTES:
            fail("trips", f"trip {t} takes {(seq[-1][2] - seq[0][2]) / 60:.1f} h")

    # --- lines: trips use the right route and visit stations in line order
    for t, seq in times.items():
        if t in KNOWN_SOURCE_TYPOS:
            continue
        stop_ids = [s for _, s, _, _ in seq]
        route = trips[t]["route_id"]
        if route in METRO_LINES:
            continue
        for s, expected in STATION_TO_ROUTE.items():
            if s in stop_ids and route != expected:
                fail("lines", f"trip {t} serves {s} but is filed under {route}, not {expected}")
        if route.startswith("WR") and CENTRAL_ONLY & set(stop_ids):
            fail("lines", f"Western trip {t} visits {sorted(CENTRAL_ONLY & set(stop_ids))}")
        if route == "CR_MAIN" and WESTERN_ONLY & set(stop_ids):
            fail("lines", f"Central trip {t} visits {sorted(WESTERN_ONLY & set(stop_ids))}")
        for line, order in (("Western", WESTERN), ("Central", CENTRAL), ("Harbour", HARBOUR)):
            pos = {s: i for i, s in enumerate(order)}
            idx = [pos[s] for s in stop_ids if s in pos]
            if idx != sorted(idx) and idx != sorted(idx, reverse=True):
                fail("lines", f"trip {t} visits {line} line stations out of order: "
                              f"{[s for s in stop_ids if s in pos]}")

    # --- source coverage
    from compile_gtfs import SOURCES
    from common import EXTRACTED
    source_trains = set()
    for name in SOURCES:
        with open(EXTRACTED / f"{name}.csv", encoding="utf-8") as f:
            source_trains |= {r["train_number"] for r in csv.DictReader(f)}
    for t in sorted(source_trains - {t.split("-")[0] for t in trips} - KNOWN_MISSING_TRAINS):
        fail("coverage", f"train {t} is in the timetables but has no trip")

    # --- shapes
    track = build_track_graph()
    lines_at = {(round(d["lat"], 5), round(d["lon"], 5)): d["lines"] for _, d in track.nodes(data=True)}
    shapes = defaultdict(list)
    for r in read("shapes.txt"):
        shapes[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
    shape_stops = {}
    for t, r in trips.items():
        if r["shape_id"] not in shapes:
            fail("shapes", f"trip {t}: shape {r['shape_id']} missing from shapes.txt")
        shape_stops.setdefault(r["shape_id"], [s for _, s, _, _ in times[t]])
    own_line = {"WR_MAIN": "WESTERN RAILWAY", "WR_DAHANU": "WESTERN RAILWAY", "CR_MAIN": "CENTRAL RAILWAY"}
    for sid, pts in shapes.items():
        pts = [(la, lo) for _, la, lo in sorted(pts)]
        seq = shape_stops.get(sid)
        if not seq:
            fail("shapes", f"shape {sid} is used by no trip")
            continue
        for end, stop in ((pts[0], seq[0]), (pts[-1], seq[-1])):
            if haversine(*end, *coord[stop]) > SHAPE_END_TOLERANCE_M:
                fail("shapes", f"{sid}: ends {haversine(*end, *coord[stop]):.0f} m from {stop}")
        for s in seq:
            if min(haversine(*coord[s], *p) for p in pts) > SHAPE_END_TOLERANCE_M:
                fail("shapes", f"{sid} passes more than {SHAPE_END_TOLERANCE_M} m from its stop {s}")
        route = next(r["route_id"] for r in trips.values() if r["shape_id"] == sid)
        want = own_line.get(route)
        if want:
            off = {l for p in pts if (key := (round(p[0], 5), round(p[1], 5))) in lines_at
                   and want not in lines_at[key] for l in lines_at[key]}
            if off:
                fail("shapes", f"{sid} ({route}) runs over {sorted(off)} tracks")

    check_metro(fail, stops, coord, trips, times, shapes, read("transfers.txt"))

    total = sum(len(v) for v in errors.values())
    for check in ("references", "stations", "trips", "lines", "coverage", "shapes", "metro"):
        problems = errors.get(check, [])
        print(f"{'FAIL' if problems else 'ok  '} {check}" + (f" ({len(problems)})" if problems else ""))
        for p in problems[:15]:
            print("      " + p)
        if len(problems) > 15:
            print(f"      ... {len(problems) - 15} more")
    print(f"known source typos excluded: {sorted(KNOWN_SOURCE_TYPOS)}; known missing trains: {sorted(KNOWN_MISSING_TRAINS)}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
