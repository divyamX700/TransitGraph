import json
import time
import os
from geopy.geocoders import Nominatim

base_dir = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted"
json_path = os.path.join(base_dir, "station_mapping.json")

with open(json_path, "r", encoding="utf-8") as f:
    mapping = json.load(f)

geolocator = Nominatim(user_agent="bomrouter_mumbai_rail_data_engine")

print(f"Starting geocoding for {len(mapping)} stations using OpenStreetMap (Nominatim)...")

success = 0
failed = []

for raw_name, data in mapping.items():
    if data["lat"] != "" and data["lon"] != "":
        continue
        
    query_name = data["normalized_name"]
    # Construct a highly specific OSM query based on Mumbai geography
    query = f"{query_name} Railway Station, Mumbai, Maharashtra"
    
    # Geographic overrides for stations outside Mumbai City/Suburban districts
    if query_name in ["Panvel", "Khandeshwar", "Mansarovar", "Kharghar", "CBD Belapur", "Seawoods Darave", "Nerul", "Juinagar", "Vashi", "Sanpada", "Turbhe", "Kopar Khairane", "Ghansoli", "Rabale", "Airoli", "Digha Gaon"]:
        query = f"{query_name} Railway Station, Navi Mumbai, Maharashtra"
    elif query_name in ["Thane", "Kalva", "Mumbra", "Diwa", "Kopar", "Dombivli", "Thakurli", "Kalyan", "Vithalwadi", "Ulhasnagar", "Ambernath", "Badlapur", "Vangani", "Shelu", "Neral", "Bhivpuri Road", "Karjat", "Palasdhari", "Kelavli", "Dolavli", "Lowjee", "Khopoli", "Shahad", "Ambivli", "Titwala", "Khadavli", "Vasind", "Asangaon", "Atgaon", "Thansit", "Khardi", "Umbermali", "Kasara"]:
        query = f"{query_name} Railway Station, Maharashtra"
    elif query_name in ["Mira Road", "Bhayandar", "Naigaon", "Vasai Road", "Nallasopara", "Virar", "Vaitarna", "Saphale", "Kelve Road", "Palghar", "Umroli", "Boisar", "Vangaon", "Dahanu Road"]:
        query = f"{query_name} Railway Station, Palghar, Maharashtra"
        if query_name in ["Mira Road", "Bhayandar"]: query = f"{query_name} Railway Station, Thane, Maharashtra"
    elif query_name in ["Targhar", "Bamandongri", "Kharkopar", "Gavhan", "Shematikhar", "Nhave Sheva", "Dronagiri", "Uran"]:
        query = f"{query_name} Railway Station, Navi Mumbai, Maharashtra"
        
    try:
        location = geolocator.geocode(query, timeout=10)
        if location:
            data["lat"] = location.latitude
            data["lon"] = location.longitude
            success += 1
            print(f"[OK] {query_name}: {location.latitude}, {location.longitude}")
        else:
            # Fallback broader query
            fallback = f"{query_name} Station, Maharashtra"
            loc2 = geolocator.geocode(fallback, timeout=10)
            if loc2:
                data["lat"] = loc2.latitude
                data["lon"] = loc2.longitude
                success += 1
                print(f"[OK-Fallback] {query_name}: {loc2.latitude}, {loc2.longitude}")
            else:
                failed.append(query_name)
                print(f"[FAILED] {query_name}")
    except Exception as e:
        print(f"[ERROR] {query_name}: {e}")
        failed.append(query_name)
        
    # Respect OSM Nominatim rate limits (1 req/sec)
    time.sleep(1.2) 

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(mapping, f, indent=4)

print(f"\nGeocoding complete! Success: {success}, Failed: {len(failed)}")
if failed:
    print(f"Failed stations: {', '.join(failed)}")
