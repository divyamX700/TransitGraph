"""shapes.txt: for every shape_id in trips.txt, route its stop sequence over the rail track
geometry in the KML (a graph of track points) and write the resulting polyline.

Stops that several lines share a name (and a pin) for, such as Dadar, sit between two sets of
tracks, so snapping a stop to the single nearest track point puts it on the wrong line half the
time. Each stop therefore gets one candidate track point per line (Western, Central, ...) and
the candidates for a whole shape are chosen together to minimise the total track length.
"""
import csv
import xml.etree.ElementTree as ET
from collections import defaultdict

import networkx as nx

import metro
from common import EXTRACTED, GTFS, haversine

KML_FILE = EXTRACTED / "rail_tracks.kml"  # track geometry, one placemark per line section
KML_NS = {"k": "http://www.opengis.net/kml/2.2"}
SNAP_PER_LINE_M = 400    # candidate track point per line within this distance of a stop
SNAP_ANY_M = 1000        # otherwise the nearest track point, if within this distance
BRIDGE_GAP_M = 500       # connect separate track components closer than this
NO_PATH = float("inf")


def build_track_graph():
    """Graph of track points; each node records which lines (KML placemark names) it lies on."""
    G = nx.Graph()
    for placemark in ET.parse(KML_FILE).getroot().findall(".//k:Placemark", KML_NS):
        coords = placemark.find(".//k:coordinates", KML_NS)
        if coords is None or not coords.text:
            continue
        line = placemark.find("k:name", KML_NS).text
        pts = [tuple(map(float, c.split(",")[:2][::-1])) for c in coords.text.split()]  # (lat, lon)
        nodes = [(round(lat, 5), round(lon, 5)) for lat, lon in pts]
        for node, (lat, lon) in zip(nodes, pts):
            G.add_node(node, lat=lat, lon=lon)
            G.nodes[node].setdefault("lines", set()).add(line)
        for (n1, p1), (n2, p2) in zip(zip(nodes, pts), zip(nodes[1:], pts[1:])):
            G.add_edge(n1, n2, weight=haversine(*p1, *p2))

    components = list(nx.connected_components(G))
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            d, n1, n2 = min((haversine(*a, *b), a, b) for a in components[i] for b in components[j])
            if d < BRIDGE_GAP_M:
                G.add_edge(n1, n2, weight=d)
    return G.subgraph(max(nx.connected_components(G), key=len)).copy()


def candidates(G, lat, lon):
    """[(track_node, snap_distance_m)]: the nearest track point on each line near the stop,
    or the nearest point of any line if none is that close. Empty if the stop is off the tracks."""
    nearest = {}  # line -> (distance, node)
    best = (NO_PATH, None)
    for node, data in G.nodes(data=True):
        d = haversine(lat, lon, data["lat"], data["lon"])
        best = min(best, (d, node), key=lambda x: x[0])
        for line in data["lines"]:
            if d < nearest.get(line, (NO_PATH,))[0]:
                nearest[line] = (d, node)
    near = {node: d for d, node in nearest.values() if d <= SNAP_PER_LINE_M}
    if near:
        return list(near.items())
    return [(best[1], best[0])] if best[0] <= SNAP_ANY_M else []


def choose_nodes(G, stop_cands, track_length):
    """Viterbi over a shape's stops: one candidate per stop (None = stop off the tracks),
    minimising snap distances plus the track length between consecutive stops."""
    layers = [c if c else [(None, 0)] for c in stop_cands]
    cost = [{n: d for n, d in layers[0]}]
    back = []
    for prev, layer in zip(layers, layers[1:]):
        step, choice = {}, {}
        for n2, snap in layer:
            options = [(cost[-1][n1] + snap + (track_length(n1, n2) if n1 and n2 else 0), n1)
                       for n1, _ in prev]
            step[n2], choice[n2] = min(options, key=lambda x: x[0])
        cost.append(step)
        back.append(choice)
    node = min(cost[-1], key=cost[-1].get)
    chosen = [node]
    for choice in reversed(back):
        node = choice[node]
        chosen.append(node)
    return chosen[::-1]


def read_shapes():
    """shape_id -> stop sequence, from the first trip using each shape."""
    shape_of = {}
    with open(GTFS / "trips.txt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            shape_of[r["trip_id"]] = r["shape_id"]
    stops_of = defaultdict(list)
    with open(GTFS / "stop_times.txt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stops_of[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"]))
    shapes = {}
    for trip, seq in stops_of.items():
        shapes.setdefault(shape_of[trip], [s for _, s in sorted(seq)])
    return shapes


def generate_shapes():
    G = build_track_graph()
    print(f"Track graph: {G.number_of_nodes()} points")
    with open(GTFS / "stops.txt", encoding="utf-8") as f:
        stops = {r["stop_id"]: (float(r["stop_lat"]), float(r["stop_lon"])) for r in csv.DictReader(f)
                 if r["stop_mode"] == "LOCAL"}  # metro shapes come from metro.py
    cands = {s: candidates(G, *ll) for s, ll in stops.items()}

    lengths = {}

    def track_length(a, b):
        if (a, b) not in lengths:
            try:
                lengths[a, b] = nx.shortest_path_length(G, a, b, weight="weight")
            except nx.NetworkXNoPath:
                lengths[a, b] = NO_PATH
        return lengths[a, b]

    shapes = {sid: seq for sid, seq in read_shapes().items() if all(st in stops for st in seq)}
    rows = []
    for shape_id, seq in shapes.items():
        nodes = choose_nodes(G, [cands[s] for s in seq], track_length)
        points = []
        for (s1, n1), (s2, n2) in zip(zip(seq, nodes), zip(seq[1:], nodes[1:])):
            if n1 and n2 and track_length(n1, n2) < NO_PATH:
                path = nx.shortest_path(G, n1, n2, weight="weight")
                points += [(G.nodes[n]["lat"], G.nodes[n]["lon"]) for n in path]
            else:  # off the tracks (Dahanu, Kasara, ...): straight line between the stations
                points += [stops[s1], stops[s2]]
                # Manual patch: this hop skips Thansit, which lies between the two.
                if {s1, s2} == {"ATGAON", "KHARDI"} and "THANSIT" in stops:
                    points.insert(-1, stops["THANSIT"])
        deduped = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
        rows += [[shape_id, lat, lon, i + 1] for i, (lat, lon) in enumerate(deduped)]

    metro_rows = metro.build()["shapes"]
    rows += metro_rows
    with open(GTFS / "shapes.txt", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
        w.writerows(rows)
    print(f"{len(shapes)} local shapes + {len({r[0] for r in metro_rows})} metro shapes, {len(rows)} points")


if __name__ == "__main__":
    generate_shapes()
