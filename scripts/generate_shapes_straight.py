import os
import csv
from collections import defaultdict

BASE_DIR = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter"
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")

def generate_straight_shapes():
    stops = {}
    with open(os.path.join(GTFS_DIR, "stops.txt"), "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stops[row["stop_id"]] = (row["stop_lat"], row["stop_lon"])
            
    shape_to_stops = {}
    trip_to_shape = {}
    with open(os.path.join(GTFS_DIR, "trips.txt"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_to_shape[row["trip_id"]] = row["shape_id"]
            
    trip_stops = defaultdict(list)
    with open(os.path.join(GTFS_DIR, "stop_times.txt"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_stops[row["trip_id"]].append((int(row["stop_sequence"]), row["stop_id"]))
            
    for trip_id, stop_list in trip_stops.items():
        stop_list.sort(key=lambda x: x[0])
        shape_id = trip_to_shape[trip_id]
        if shape_id not in shape_to_stops:
            shape_to_stops[shape_id] = [s[1] for s in stop_list]
            
    shapes_rows = []
    for shape_id, stp_seq in shape_to_stops.items():
        for i, stop_id in enumerate(stp_seq):
            lat, lon = stops[stop_id]
            shapes_rows.append([shape_id, lat, lon, i+1])
            
    path = os.path.join(GTFS_DIR, "shapes.txt")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
        writer.writerows(shapes_rows)
        
    print(f"Generated shapes.txt as point-to-point sequences with {len(shapes_rows)} points!")

if __name__ == "__main__":
    generate_straight_shapes()
