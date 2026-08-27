import os
import json
import csv
import glob
import hashlib
from collections import defaultdict

BASE_DIR = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter"
DATA_DIR = os.path.join(BASE_DIR, "data", "extracted")
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")

os.makedirs(GTFS_DIR, exist_ok=True)

def write_csv(filename, headers, rows):
    path = os.path.join(GTFS_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def compile_stage_1():
    print("Stage 1: Compiling GTFS Structures...")
    
    write_csv("agency.txt", 
              ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang"],
              [["CR", "Central Railway", "https://cr.indianrailways.gov.in/", "Asia/Kolkata", "en"],
               ["WR", "Western Railway", "https://wr.indianrailways.gov.in/", "Asia/Kolkata", "en"]])
               
    with open(os.path.join(DATA_DIR, "station_mapping.json"), "r", encoding="utf-8") as f:
        station_map = json.load(f)
        
    stops_rows = []
    raw_to_norm = {}
    
    for norm_name, data in station_map.items():
        stop_id = norm_name.replace(" ", "_").upper()
        for raw in data.get("raw_names", [norm_name]):
            raw_to_norm[raw.strip()] = stop_id
        raw_to_norm[norm_name] = stop_id
        stops_rows.append([stop_id, norm_name, data["lat"], data["lon"]])
        
    write_csv("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"], stops_rows)
    
    routes = {
        "central": ["CR", "CR_MAIN", "Central Line", "2"],
        "harbour": ["CR", "CR_HARBOUR", "Harbour Line", "2"],
        "trans_harbour": ["CR", "CR_TRANS", "Trans-Harbour Line", "2"],
        "uran": ["CR", "CR_PORT", "Port Line", "2"],
        "western": ["WR", "WR_MAIN", "Western Line", "2"],
        "western_dahanu": ["WR", "WR_DAHANU", "Western Dahanu Line", "2"]
    }
    
    route_rows = []
    for k, v in routes.items():
        route_rows.append([v[1], v[0], v[1], v[2], v[3]])
    write_csv("routes.txt", ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"], route_rows)
    
    trips_rows = []
    stop_times_rows = []
    
    write_csv("calendar.txt", 
              ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"],
              [["weekday", "1", "1", "1", "1", "1", "1", "0", "20240101", "20261231"]])

    processed_trips = set()
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    
    for file in csv_files:
        filename = os.path.basename(file)
        route_key = "central"
        for k in routes.keys():
            if k in filename:
                route_key = k
                break
        route_id = routes[route_key][1]
        direction = "0" if "up" in filename.lower() else "1"
        
        train_data = defaultdict(list)
        
        with open(file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                train_num = row.get("train_number", "").strip()
                station = row.get("station", "").strip()
                time_str = row.get("time", "").strip()
                
                if train_num and station and time_str and time_str != "...":
                    train_data[train_num].append((station, time_str))
                    
        for train_num, stops in train_data.items():
            if train_num in processed_trips: continue
            
            trip_stop_times = []
            for station, time_str in stops:
                stop_id = raw_to_norm.get(station, station.replace(" ", "_").upper())
                parts = time_str.split(":")
                if len(parts) == 2:
                    time_fmt = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
                else: continue
                trip_stop_times.append({
                    "raw_time": time_str,
                    "fmt_time": time_fmt,
                    "stop_id": stop_id
                })
                
            trip_hours = [int(ts["raw_time"].split(":")[0]) for ts in trip_stop_times]
            if not trip_hours: continue
            crosses_midnight = (max(trip_hours) - min(trip_hours)) >= 18
            
            def time_val(ts):
                h, m = map(int, ts["raw_time"].split(":"))
                if crosses_midnight and h < 12:
                    h += 24
                return h * 60 + m
                
            trip_stop_times.sort(key=time_val)
            
            final_stop_times = []
            for i, st in enumerate(trip_stop_times):
                final_stop_times.append([train_num, st["fmt_time"], st["fmt_time"], st["stop_id"], str(i+1)])
                
            if final_stop_times:
                # Use a hash of the complete stop sequence to uniquely identify the physical path
                # Generate a unique shape ID for this sequence of stops
                stop_ids = [st["stop_id"] for st in trip_stop_times]
                shape_seq = "_".join(stop_ids)
                hash_suffix = hashlib.md5(shape_seq.encode()).hexdigest()[:4]
                shape_id = f"SHP_{route_id}_{stop_ids[0]}_TO_{stop_ids[-1]}_{hash_suffix}"
                
                trips_rows.append([route_id, "weekday", train_num, direction, shape_id])
                stop_times_rows.extend(final_stop_times)
                processed_trips.add(train_num)
                    
    write_csv("trips.txt", ["route_id", "service_id", "trip_id", "direction_id", "shape_id"], trips_rows)
    write_csv("stop_times.txt", ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"], stop_times_rows)
    print(f"Generated GTFS structures! {len(trips_rows)} trips, {len(stop_times_rows)} stop times.")

if __name__ == "__main__":
    compile_stage_1()
