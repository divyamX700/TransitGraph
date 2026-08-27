import pandas as pd
import os

file_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\raw_excel\1777550323377-DN HB REVISED PTT WEF 01.05.2026.xlsx"
out_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted\harbour_dn.csv"
stations_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted\harbour_dn_stations.txt"

os.makedirs(os.path.dirname(out_path), exist_ok=True)

print(f"Reading {file_path}...")
df = pd.read_excel(file_path, header=None)

extracted_data = []
unique_stations = set()

in_block = False
train_columns = {} 

for idx, row in df.iterrows():
    col0_val = str(row[0]).strip()
    
    if col0_val.upper() in ['STATION', 'STATIONS']:
        train_columns = {}
        for col_idx in range(1, len(row)):
            val = str(row[col_idx]).strip()
            if val != 'nan' and val != '':
                train_num = val.split('\n')[0].strip()
                train_columns[col_idx] = train_num
        in_block = True
        continue
    
    # Skip overarching headers (Checking for CSMT and PANVEL/GOREGAON)
    if "CSMT" in col0_val.upper() and ("PANVEL" in col0_val.upper() or "GOREGAON" in col0_val.upper()):
        continue
    if col0_val == 'nan' or col0_val == '':
        continue
        
    if in_block:
        station_name = col0_val
        unique_stations.add(station_name)
        
        for col_idx, train_num in train_columns.items():
            time_val = str(row[col_idx]).strip()
            
            if time_val != 'nan' and time_val != '' and time_val != '…' and time_val != '...':
                # Enforce that it is actually a time value (filters out markers like "TNA")
                if ":" in time_val:
                    if len(time_val.split(':')) == 3: 
                        time_val = ":".join(time_val.split(':')[:2])
                    
                    extracted_data.append({
                        'train_number': train_num,
                        'station': station_name,
                        'time': time_val
                    })

out_df = pd.DataFrame(extracted_data)
out_df.to_csv(out_path, index=False)

with open(stations_path, "w", encoding="utf-8") as f:
    for st in sorted(list(unique_stations)):
        f.write(st + "\n")

print(f"Success!")
print(f"Extracted {len(out_df)} stop times.")
print(f"Total unique trains: {len(out_df['train_number'].unique())}")
print(f"Total unique stations: {len(unique_stations)}")
print(f"Saved to: {out_path}")
