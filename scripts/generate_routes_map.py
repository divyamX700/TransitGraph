"""Folium map of every station and shape in data/gtfs, for eyeballing the data.
Writes scratch/routes_map.html (git-ignored)."""
import csv
from collections import defaultdict

import folium

from common import GTFS, ROOT

m = folium.Map(location=[19.0760, 72.8777], zoom_start=10, tiles="CartoDB positron")

with open(GTFS / "stops.txt", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        folium.CircleMarker(
            location=(float(row["stop_lat"]), float(row["stop_lon"])), radius=4,
            tooltip=row["stop_name"], color="#e74c3c", fill=True, fill_color="#e74c3c",
        ).add_to(m)

shapes = defaultdict(list)
with open(GTFS / "shapes.txt", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        shapes[row["shape_id"]].append(
            (int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
for shape_id, points in shapes.items():
    coords = [(lat, lon) for _, lat, lon in sorted(points)]
    folium.PolyLine(coords, weight=3, color="#2980b9", opacity=0.7, tooltip=shape_id).add_to(m)

out = ROOT / "scratch" / "routes_map.html"
out.parent.mkdir(exist_ok=True)
m.save(out)
print(f"wrote {out}")
