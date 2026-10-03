"""Fill in lat/lon for stations in data/station_mapping.json that have none yet, using
OpenStreetMap Nominatim (max 1 request/second). Results are guesses: check each one on a map
(generate_routes_map.py) before trusting it."""
import json
import time

from geopy.geocoders import Nominatim

from common import STATION_MAPPING

mapping = json.load(open(STATION_MAPPING, encoding="utf-8"))
geolocator = Nominatim(user_agent="transitgraph-data-pipeline")

for name, station in mapping.items():
    if station.get("lat") not in (None, ""):
        continue
    location = geolocator.geocode(f"{name} railway station, Maharashtra, India", timeout=10)
    if location is None:
        print(f"[not found] {name}")
    else:
        station["lat"], station["lon"] = location.latitude, location.longitude
        print(f"[ok] {name}: {location.latitude}, {location.longitude} ({location.address[:60]})")
    time.sleep(1.2)

with open(STATION_MAPPING, "w", encoding="utf-8") as f:
    json.dump(mapping, f, indent=4, ensure_ascii=False)
