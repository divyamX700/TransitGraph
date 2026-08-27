import pandas as pd
import os

def ingest_file(file_path, out_path, stations_path):
    print(f"Reading {os.path.basename(file_path)}...")
    df = pd.read_excel(file_path, header=None)
    
    extracted_data = []
    unique_stations = set()
    in_block = False
    train_columns = {}
    
    for idx, row in df.iterrows():
        col0_val = str(row[0]).strip()
        
        # Check if the row is the station header
        if "STATION" in col0_val.upper() or "TR.NO" in col0_val.upper() or "TRAIN NO" in col0_val.upper():
            train_columns = {}
            for col_idx in range(1, len(row)):
                val = str(row[col_idx]).strip()
                if val != 'nan' and val != '':
                    first_line = val.split('\n')[0].strip()
                    train_num = first_line.split()[-1]
                    train_columns[col_idx] = train_num
            in_block = True
            continue
        
        if col0_val == 'nan' or col0_val == '':
            continue
            
        if in_block:
            station_name = col0_val
            unique_stations.add(station_name)
            
            for col_idx, train_num in train_columns.items():
                time_val = str(row[col_idx]).strip()
                if time_val != 'nan' and time_val != '' and time_val != '…' and time_val != '...':
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
            
    print(f"  -> Extracted {len(out_df)} stop times, {len(out_df['train_number'].unique())} trains, {len(unique_stations)} stations.")

files = [
    ("1781160975368-PORT LINE PTT WEF 15.12.2025.xlsx", "port_line"),
    ("1781174782507-THB PTT wef 13.01.2024.xlsx", "trans_harbour")
]

base_dir = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data"
for f_name, prefix in files:
    in_p = os.path.join(base_dir, "raw_excel", f_name)
    out_p = os.path.join(base_dir, "extracted", f"{prefix}.csv")
    stat_p = os.path.join(base_dir, "extracted", f"{prefix}_stations.txt")
    
    ingest_file(in_p, out_p, stat_p)
