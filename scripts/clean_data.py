import pandas as pd
import glob
import os
import json

base_dir = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted"
csv_files = glob.glob(os.path.join(base_dir, "*.csv"))

all_stations = set()

def is_garbage(name):
    name_str = str(name)
    name_upper = name_str.upper()
    # Drop garbled merged blocks (where the Excel converter mashed 30 stations into one cell)
    if len(name_str) > 30 and "\n" in name_str: return True 
    # Drop overarching headers that leaked in
    if "LADIES ONLY" in name_upper or "TIME TABLE" in name_upper: return True
    if name_upper.startswith("TRAIN NO") or name_upper.startswith("STATION"): return True
    if "W.E.F" in name_upper: return True
    return False

for f in csv_files:
    print(f"Cleaning {os.path.basename(f)}...")
    df = pd.read_csv(f)
    
    # 1. Pad times (e.g. "3:56" -> "03:56")
    def pad_time(t):
        t = str(t).strip()
        parts = t.split(':')
        if len(parts) > 0 and len(parts[0]) == 1:
            parts[0] = "0" + parts[0]
        return ":".join(parts)
    
    df['time'] = df['time'].apply(pad_time)
    
    # 2. Filter garbage stations
    df = df[~df['station'].apply(is_garbage)]
    
    # Save back
    df.to_csv(f, index=False)
    
    # Collect unique stations
    all_stations.update(df['station'].unique())

# 3. Create a unified, normalized station mapping based on LLM knowledge
mapping = {}
for st in all_stations:
    st_clean = str(st).replace("\n", " ").strip()
    
    # Map Trans Harbour Codes and normalize weird names
    if st_clean == "TNA": mapped = "Thane"
    elif st_clean == "AIRL": mapped = "Airoli"
    elif st_clean == "RABE": mapped = "Rabale"
    elif st_clean == "GNSL": mapped = "Ghansoli"
    elif st_clean == "KPHN": mapped = "Kopar Khairane"
    elif st_clean == "TUH": mapped = "Turbhe"
    elif st_clean == "SNPD": mapped = "Sanpada"
    elif st_clean == "VSH": mapped = "Vashi"
    elif st_clean == "JNJ": mapped = "Juinagar"
    elif st_clean == "NEU": mapped = "Nerul"
    elif st_clean == "SWDV": mapped = "Seawoods Darave"
    elif st_clean == "BEPR": mapped = "CBD Belapur"
    elif st_clean == "KHAG": mapped = "Kharghar"
    elif st_clean == "MANR": mapped = "Mansarovar"
    elif st_clean == "KNDS": mapped = "Khandeshwar"
    elif st_clean == "PNVL": mapped = "Panvel"
    elif st_clean == "DIGH": mapped = "Digha Gaon"
    elif st_clean.upper() == "MUMBAI CSMT": mapped = "CSMT"
    elif st_clean.upper() == "M'BAI CENTRAL (L)": mapped = "Mumbai Central"
    elif st_clean.upper() == "SEAWOODS DARAVE KARAVE": mapped = "Seawoods Darave"
    else: 
        # Standard Title Case for normal names like "ANDHERI" -> "Andheri"
        mapped = st_clean.title()
    
    mapping[st_clean] = {
        "raw_name": st_clean,
        "normalized_name": mapped,
        "lat": "",
        "lon": ""
    }

# Sort mapping alphabetically by raw_name for easy reading
sorted_mapping = dict(sorted(mapping.items()))

out_json = os.path.join(base_dir, "station_mapping.json")
with open(out_json, "w", encoding="utf-8") as jf:
    json.dump(sorted_mapping, jf, indent=4)

print(f"Successfully cleaned all CSVs and generated unified mapping with {len(mapping)} stations.")
