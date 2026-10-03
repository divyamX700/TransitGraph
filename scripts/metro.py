"""Metro and monorail lines -> GTFS rows and shapes.

Input: data/metro/lines.json (service definitions) and data/metro/osm/*.json (stations and track
geometry from OpenStreetMap). The operators publish first/last trains and headways rather than
a timetable, so trips are generated: trains leave each terminus at the published first time,
then every headway until the last published departure, and run at a constant speed along
the track (the published end-to-end time spread over the stations in proportion to track length).
"""
import hashlib
import json
import math
import re

import networkx as nx

from common import DATA

LINES_FILE = DATA / "metro" / "lines.json"
OSM_DIR = DATA / "metro" / "osm"
SNAP_MAX_M = 250        # a station further than this from the line's track is a data error
MIN_SEGMENT_MIN = 1.0   # no hop between two stations is shorter than a minute

AGENCIES = {
    "MMOPL": ("Mumbai Metro One Pvt Ltd", "https://www.mumbaimetroone.com/"),
    "MMMOCL": ("Maha Mumbai Metro Operation Corporation", "https://www.mmmocl.co.in/"),
    "MMRC": ("Mumbai Metro Rail Corporation", "https://www.mmrcl.com/"),
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def clean_name(name):
    """OSM names carry routing hints ("Marol Naka (Line 1)", "Dahisar (East) [Line 7]")."""
    name = re.sub(r"\s*\[[^\]]*\]", "", name)
    name = re.sub(r"\s*\((Line \w+|eastbound|westbound)\)", "", name)
    return " ".join(name.split())


def stop_id(line_id, name):
    return f"{line_id}_" + re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def parse_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmmss(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def headway_at(bands, minute):
    for start, end, headway in bands:
        if parse_minutes(start) <= minute < parse_minutes(end):
            return headway
    raise ValueError(f"no headway band covers {minute // 60:02d}:{minute % 60:02d}")


def track_graph(osm_names):
    G = nx.Graph()
    for osm in osm_names:
        for way in json.load(open(OSM_DIR / f"{osm}.json", encoding="utf-8"))["ways"]:
            nodes = [(round(lat, 5), round(lon, 5)) for lat, lon in way]
            for node, (lat, lon) in zip(nodes, way):
                G.add_node(node, lat=lat, lon=lon)
            for (a, p), (b, q) in zip(zip(nodes, way), zip(nodes[1:], way[1:])):
                if a != b:
                    G.add_edge(a, b, weight=haversine(*p, *q))
    return G


def load_line(config):
    """Stations in line order, each with coordinates, and the track between consecutive stations."""
    stations = []
    for part in config["parts"]:
        stops = json.load(open(OSM_DIR / f"{part['osm']}.json", encoding="utf-8"))["stops"]
        if part.get("reverse"):
            stops = stops[::-1]
        for s in stops[part.get("skip", 0):]:
            name = clean_name(s["name"])
            stations.append({"name": config.get("rename", {}).get(name, name), "lat": s["lat"], "lon": s["lon"]})
    ids = [stop_id(config["id"], s["name"]) for s in stations]
    assert len(set(ids)) == len(ids), f"{config['id']}: duplicate station names {ids}"
    for s, i in zip(stations, ids):
        s["id"] = i

    G = track_graph([p["osm"] for p in config["parts"]])
    nodes = list(G.nodes(data=True))
    snapped = []
    for s in stations:
        d, node = min((haversine(s["lat"], s["lon"], data["lat"], data["lon"]), n) for n, data in nodes)
        assert d <= SNAP_MAX_M, f"{config['id']}: {s['name']} is {d:.0f} m from the track"
        snapped.append(node)

    segments = []  # per consecutive pair: (metres, [(lat, lon), ...])
    for a, b in zip(snapped, snapped[1:]):
        try:
            path = nx.shortest_path(G, a, b, weight="weight")
            metres = nx.shortest_path_length(G, a, b, weight="weight")
        except nx.NetworkXNoPath:  # track data has a gap: join the stations directly
            path, metres = [a, b], haversine(*a, *b)
        segments.append((metres, [(G.nodes[n]["lat"], G.nodes[n]["lon"]) for n in path]))
    return stations, segments


def build():
    """Everything the GTFS needs from the active metro lines:
    {"agencies", "routes", "stops", "trips", "stop_times", "shapes"} as lists of rows."""
    lines = json.load(open(LINES_FILE, encoding="utf-8"))["lines"]
    out = {k: [] for k in ("agencies", "routes", "stops", "trips", "stop_times", "shapes")}
    used_agencies = set()
    for config in lines:
        if not config.get("active", True):
            continue
        stations, segments = load_line(config)
        metres = [m for m, _ in segments]
        total_m = sum(metres)
        total_min = config.get("end_to_end_minutes") or total_m / 1000 / config["avg_speed_kmh"] * 60
        minutes = [max(MIN_SEGMENT_MIN, total_min * m / total_m) for m in metres]
        offsets = [0.0]
        for m in minutes:
            offsets.append(offsets[-1] + m)

        used_agencies.add(config["agency"])
        route = config["id"]
        out["routes"].append([route, config["agency"], config["short_name"], config["name"], 1, config["color"]])
        for s in stations:
            out["stops"].append([s["id"], s["name"], s["lat"], s["lon"], config["mode"], route])

        terminals = {stations[0]["name"]: 0, stations[-1]["name"]: 1}
        for direction in config["directions"]:
            d = terminals[direction["from"]]
            seq = stations if d == 0 else stations[::-1]
            offs = offsets if d == 0 else [offsets[-1] - o for o in offsets[::-1]]
            stop_ids = [s["id"] for s in seq]
            shape_id = f"SHP_{route}_{stop_ids[0]}_TO_{stop_ids[-1]}_" + hashlib.md5("_".join(stop_ids).encode()).hexdigest()[:4]

            points = []
            for _, path in (segments if d == 0 else [(m, p[::-1]) for m, p in segments[::-1]]):
                points += path
            deduped = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
            out["shapes"] += [[shape_id, lat, lon, i + 1] for i, (lat, lon) in enumerate(deduped)]

            minute, last = parse_minutes(direction["first"]), parse_minutes(direction["last"])
            departures = []
            while minute < last:
                departures.append(minute)
                minute += headway_at(config["headway_minutes"], int(minute))
            departures.append(last)  # the published last train always runs
            for minute in departures:
                trip_id = f"{route}-{d}-{int(minute) // 60:02d}{int(minute) % 60:02d}"
                out["trips"].append([route, "weekday", trip_id, d, shape_id])
                for i, (stop, offset) in enumerate(zip(stop_ids, offs)):
                    t = round(minute + offset)
                    out["stop_times"].append([trip_id, hhmmss(t), hhmmss(t), stop, i + 1])
    out["agencies"] = [[a, AGENCIES[a][0], AGENCIES[a][1], "Asia/Kolkata", "en"] for a in sorted(used_agencies)]
    return out
