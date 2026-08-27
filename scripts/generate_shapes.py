import os
import json
import csv
import math
import requests
import networkx as nx
from collections import defaultdict

BASE_DIR = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter"
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")
OSM_FILE = os.path.join(BASE_DIR, "data", "extracted", "osm_rail_ways.json")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def fetch_osm_rails():
    if os.path.exists(OSM_FILE):
        with open(OSM_FILE, "r") as f: return json.load(f)
    print("Downloading railway tracks from Overpass... this might take 30s")
    bbox = "18.5,72.7,20.2,73.8"
    query = f"""
    [out:json][timeout:60];
    way["railway"="rail"]({bbox});
    (._;>;);
    out body;
    """
    res = requests.post("https://overpass.kumi.systems/api/interpreter", data={'data': query}, headers={'User-Agent': 'BomRouterGTFS/1.0'})
    if res.status_code != 200:
        print(f"Overpass API Error {res.status_code}: {res.text[:200]}")
        raise Exception("Failed to fetch OSM data")
    data = res.json()
    with open(OSM_FILE, "w") as f: json.dump(data, f)
    return data
    
def generate_shapes():
    osm_data = fetch_osm_rails()
    print("Building track network graph...")
    
    nodes = {}
    for el in osm_data["elements"]:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])
            
    G = nx.Graph()
    for el in osm_data["elements"]:
        if el["type"] == "way":
            nds = el.get("nodes", [])
            for i in range(len(nds)-1):
                n1, n2 = nds[i], nds[i+1]
                if n1 in nodes and n2 in nodes:
                    dist = haversine(nodes[n1][0], nodes[n1][1], nodes[n2][0], nodes[n2][1])
                    G.add_edge(n1, n2, weight=dist)
                    
    largest_cc = max(nx.connected_components(G), key=len)
    G = G.subgraph(largest_cc).copy()
    
    print(f"Graph built with {G.number_of_nodes()} track nodes.")
    
    stops = {}
    with open(os.path.join(GTFS_DIR, "stops.txt"), "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stops[row["stop_id"]] = (float(row["stop_lat"]), float(row["stop_lon"]))
            
    stop_to_node = {}
    graph_nodes_list = list(G.nodes())
    for stop_id, (lat, lon) in stops.items():
        min_dist = float('inf')
        best_node = None
        for n in graph_nodes_list:
            d = haversine(lat, lon, nodes[n][0], nodes[n][1])
            if d < min_dist:
                min_dist = d
                best_node = n
        stop_to_node[stop_id] = best_node
        
    print("Stations snapped to tracks.")
    
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
            
    print(f"Routing {len(shape_to_stops)} unique shapes...")
    shapes_rows = []
    
    for shape_id, stp_seq in shape_to_stops.items():
        pt_seq = 1
        for i in range(len(stp_seq)-1):
            n1 = stop_to_node[stp_seq[i]]
            n2 = stop_to_node[stp_seq[i+1]]
            try:
                path = nx.shortest_path(G, n1, n2, weight='weight')
                # Avoid duplicating the node where segments meet
                if i > 0: path = path[1:] 
                for node_id in path:
                    lat, lon = nodes[node_id]
                    shapes_rows.append([shape_id, lat, lon, pt_seq])
                    pt_seq += 1
            except nx.NetworkXNoPath:
                if i == 0:
                    lat1, lon1 = nodes[n1]
                    shapes_rows.append([shape_id, lat1, lon1, pt_seq])
                    pt_seq += 1
                lat2, lon2 = nodes[n2]
                shapes_rows.append([shape_id, lat2, lon2, pt_seq])
                pt_seq += 1
                
    path = os.path.join(GTFS_DIR, "shapes.txt")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
        writer.writerows(shapes_rows)
        
    print(f"Successfully generated shapes.txt with {len(shapes_rows)} points!")

if __name__ == "__main__":
    generate_shapes()
