import os
import csv
import math
import networkx as nx
import xml.etree.ElementTree as ET
from collections import defaultdict

BASE_DIR = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter"
GTFS_DIR = os.path.join(BASE_DIR, "data", "gtfs")
KML_FILE = os.path.join(BASE_DIR, "data", "extracted", "46f53a20-aebb-4096-bf33-c6d9d87afaca.kml")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_kml_shapes():
    print("Parsing KML track geometries...")
    tree = ET.parse(KML_FILE)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    lines = []
    for placemark in root.findall('.//kml:Placemark', ns):
        coords = placemark.find('.//kml:coordinates', ns)
        if coords is not None and coords.text:
            raw_coords = coords.text.strip().split()
            pts = []
            for c in raw_coords:
                parts = c.split(',')
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    pts.append((lat, lon))
            if pts: lines.append(pts)
            
    print(f"Extracted {len(lines)} track linestrings. Building Graph...")
    
    G = nx.Graph()
    def node_id(lat, lon):
        return (round(lat, 5), round(lon, 5))
        
    for pts in lines:
        for i in range(len(pts)-1):
            n1 = node_id(*pts[i])
            n2 = node_id(*pts[i+1])
            G.add_node(n1, lat=pts[i][0], lon=pts[i][1])
            G.add_node(n2, lat=pts[i+1][0], lon=pts[i+1][1])
            dist = haversine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            G.add_edge(n1, n2, weight=dist)
            
    # Bridge disconnected components
    components = list(nx.connected_components(G))
    if len(components) > 1:
        print(f"Graph has {len(components)} disconnected components. Bridging gaps...")
        for i in range(len(components)):
            for j in range(i+1, len(components)):
                c1_nodes = list(components[i])
                c2_nodes = list(components[j])
                min_dist = float('inf')
                best_pair = None
                for n1 in c1_nodes:
                    for n2 in c2_nodes:
                        d = haversine(n1[0], n1[1], n2[0], n2[1])
                        if d < min_dist:
                            min_dist = d
                            best_pair = (n1, n2)
                if best_pair and min_dist < 500:
                    G.add_edge(best_pair[0], best_pair[1], weight=min_dist)
                    
    # Only keep largest connected component just to be safe
    largest_cc = max(nx.connected_components(G), key=len)
    G = G.subgraph(largest_cc).copy()
    print(f"Graph fully connected with {G.number_of_nodes()} track nodes.")
    
    stops = {}
    with open(os.path.join(GTFS_DIR, "stops.txt"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stops[row["stop_id"]] = (float(row["stop_lat"]), float(row["stop_lon"]))
            
    stop_to_node = {}
    graph_nodes = list(G.nodes(data=True))
    for stop_id, (lat, lon) in stops.items():
        min_dist = float('inf')
        best_node = None
        for n, data in graph_nodes:
            d = haversine(lat, lon, data['lat'], data['lon'])
            if d < min_dist:
                min_dist = d
                best_node = n
        if min_dist > 1000:
            stop_to_node[stop_id] = None
        else:
            stop_to_node[stop_id] = best_node
        
    print("Stations snapped to KML tracks.")
    
    shape_to_stops = {}
    trip_to_shape = {}
    with open(os.path.join(GTFS_DIR, "trips.txt"), "r") as f:
        for row in csv.DictReader(f):
            trip_to_shape[row["trip_id"]] = row["shape_id"]
            
    trip_stops = defaultdict(list)
    with open(os.path.join(GTFS_DIR, "stop_times.txt"), "r") as f:
        for row in csv.DictReader(f):
            trip_stops[row["trip_id"]].append((int(row["stop_sequence"]), row["stop_id"]))
            
    for trip_id, stop_list in trip_stops.items():
        stop_list.sort(key=lambda x: x[0])
        shape_id = trip_to_shape[trip_id]
        if shape_id not in shape_to_stops:
            shape_to_stops[shape_id] = [s[1] for s in stop_list]
            
    print(f"Routing {len(shape_to_stops)} unique shapes over KML tracks...")
    shapes_rows = []
    
    for shape_id, stp_seq in shape_to_stops.items():
        pt_seq = 1
        for i in range(len(stp_seq)-1):
            s1 = stp_seq[i]
            s2 = stp_seq[i+1]
            n1 = stop_to_node[s1]
            n2 = stop_to_node[s2]
            
            if n1 is not None and n2 is not None:
                try:
                    path = nx.shortest_path(G, n1, n2, weight='weight')
                    if pt_seq > 1: path = path[1:] # avoid duplicate node at joint
                    for node_id in path:
                        lat, lon = G.nodes[node_id]['lat'], G.nodes[node_id]['lon']
                        shapes_rows.append([shape_id, lat, lon, pt_seq])
                        pt_seq += 1
                except nx.NetworkXNoPath:
                    lat1, lon1 = G.nodes[n1]['lat'], G.nodes[n1]['lon']
                    lat2, lon2 = G.nodes[n2]['lat'], G.nodes[n2]['lon']
                    if pt_seq == 1:
                        shapes_rows.append([shape_id, lat1, lon1, pt_seq])
                        pt_seq += 1
                    shapes_rows.append([shape_id, lat2, lon2, pt_seq])
                    pt_seq += 1
            else:
                # Fallback to straight line for outlier stations (e.g. Dahanu, Kasara)
                if pt_seq == 1:
                    shapes_rows.append([shape_id, stops[s1][0], stops[s1][1], pt_seq])
                    pt_seq += 1
                
                # USER PATCH: Force connection through Thansit if skipping it
                if (s1 == 'ATGAON' and s2 == 'KHARDI') or (s1 == 'KHARDI' and s2 == 'ATGAON'):
                    if 'THANSIT' in stops:
                        shapes_rows.append([shape_id, stops['THANSIT'][0], stops['THANSIT'][1], pt_seq])
                        pt_seq += 1
                        
                shapes_rows.append([shape_id, stops[s2][0], stops[s2][1], pt_seq])
                pt_seq += 1
                
    path = os.path.join(GTFS_DIR, "shapes.txt")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
        writer.writerows(shapes_rows)
        
    print(f"Successfully generated shapes.txt with {len(shapes_rows)} precise geographic points!")

if __name__ == "__main__":
    generate_kml_shapes()
