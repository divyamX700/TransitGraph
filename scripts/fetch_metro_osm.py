"""Download the stations and track geometry of the metro and monorail lines from OpenStreetMap
(Overpass API) into data/metro/osm/<line>.json. The results are committed, so rebuilding the
GTFS does not need the network; run this only to refresh them.

Each file: {"relation": id, "name": ..., "stops": [{"name", "lat", "lon"}, ...] (in line order),
            "ways": [[[lat, lon], ...], ...] (track segments)}
"""
import json
import sys
import time
import urllib.parse
import urllib.request

from common import DATA

OUT = DATA / "metro" / "osm"
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

# line id -> OSM route relation (one direction is enough: stops come in line order)
RELATIONS = {
    "M1": 3808111,     # Line 1, Versova -> Ghatkopar
    "M2A": 13989913,   # Line 2A, Dahisar East -> Andheri West
    "M3": 7898597,     # Line 3 (Aqua), Aarey JVLR -> Cuffe Parade
    "M7": 13989915,    # Line 7, Dahisar East -> Gundavali
    "M9": 20403865,    # Line 9, Dahisar East -> Kashigaon (joined to Line 7 in lines.json)
    "M2B": 20403809,   # Line 2B, Chembur -> Mandale (only part of it is open)
    "NM1": 16533436,   # Navi Mumbai Metro Line 1, CBD Belapur -> Pendhar
}


def overpass(query, tries=4):
    for attempt in range(tries):
        for endpoint in ENDPOINTS:
            try:
                req = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"data": query}).encode(),
                                             headers={"User-Agent": "transitgraph-data-pipeline/1.0"})
                return json.load(urllib.request.urlopen(req, timeout=100))
            except Exception as e:
                print(f"  {endpoint}: {str(e)[:70]}", file=sys.stderr)
                time.sleep(2 + attempt * 3)
    sys.exit("Overpass API unavailable")


def fetch(line, rel_id):
    relation = overpass(f"[out:json][timeout:90];rel({rel_id});out body;")["elements"][0]
    stop_ids = [m["ref"] for m in relation["members"] if m["type"] == "node" and m["role"] == "stop"]
    nodes = {e["id"]: e for e in overpass(
        "[out:json][timeout:90];node(id:" + ",".join(map(str, stop_ids)) + ");out body;")["elements"]}
    ways = overpass(f"[out:json][timeout:90];rel({rel_id});way(r);out geom;")["elements"]
    return {
        "relation": rel_id,
        "name": relation["tags"]["name"],
        "stops": [{"name": nodes[i]["tags"]["name"], "lat": nodes[i]["lat"], "lon": nodes[i]["lon"]} for i in stop_ids],
        "ways": [[[p["lat"], p["lon"]] for p in w["geometry"]] for w in ways if "geometry" in w],
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for line, rel_id in RELATIONS.items():
        data = fetch(line, rel_id)
        with open(OUT / f"{line}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"{line}: {len(data['stops'])} stops, {len(data['ways'])} track ways ({data['name']})")
