import json
import folium
import os

base_dir = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted"
json_path = os.path.join(base_dir, "station_mapping.json")

with open(json_path, "r", encoding="utf-8") as f:
    mapping = json.load(f)

# Center the map on Mumbai
m = folium.Map(location=[19.0760, 72.8777], zoom_start=10, tiles="CartoDB positron")

mapped_count = 0
for norm_name, data in mapping.items():
    lat = data.get("lat")
    lon = data.get("lon")
    if lat and lon:
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=6,
            popup=norm_name,
            tooltip=norm_name,
            color="#3186cc",
            fill=True,
            fill_color="#3186cc"
        ).add_to(m)
        mapped_count += 1

out_file = os.path.join(base_dir, "mumbai_rail_map.html")
m.save(out_file)
print(f"Interactive map successfully generated with {mapped_count} stations at: {out_file}")
