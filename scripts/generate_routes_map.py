import csv
import folium
import os
from collections import defaultdict

BASE_DIR = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter"
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")

def generate_routes_map():
    m = folium.Map(location=[19.0760, 72.8777], zoom_start=10, tiles="CartoDB positron")
    
    # Plot stations
    stops = {}
    with open(os.path.join(GTFS_DIR, "stops.txt"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stops[row["stop_id"]] = (float(row["stop_lat"]), float(row["stop_lon"]))
            folium.CircleMarker(
                location=stops[row["stop_id"]],
                radius=4, popup=row["stop_name"], tooltip=row["stop_name"],
                color="#e74c3c", fill=True, fill_color="#e74c3c"
            ).add_to(m)
            
    # Plot shapes
    shapes = defaultdict(list)
    with open(os.path.join(GTFS_DIR, "shapes.txt"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            shapes[row["shape_id"]].append((
                int(row["shape_pt_sequence"]), 
                float(row["shape_pt_lat"]), 
                float(row["shape_pt_lon"])
            ))
            
    for shape_id, points in shapes.items():
        points.sort(key=lambda x: x[0])
        coords = [(lat, lon) for seq, lat, lon in points]
        folium.PolyLine(
            coords, weight=3, color="#2980b9", opacity=0.7, tooltip=shape_id
        ).add_to(m)

    out_file = os.path.join(BASE_DIR, "data", "extracted", "mumbai_routes_map.html")
    m.save(out_file)
    print(f"Routes map generated successfully at: {out_file}")

if __name__ == "__main__":
    generate_routes_map()
