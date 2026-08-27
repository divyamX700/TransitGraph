import pandas as pd
import os

file_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\raw_excel\1728294831372-SUB PTT DN ML'24.xlsx"
out_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted\central_dn.csv"
stations_path = r"c:\Users\Divyam Kulshrestha\Desktop\BomRouter\data\extracted\central_dn_stations.txt"

os.makedirs(os.path.dirname(out_path), exist_ok=True)

print("Reading Excel file...")
df = pd.read_excel(file_path, header=None)

extracted_data = []
unique_stations = set()

in_block = False
train_columns = {} # maps column index -> train_number

for idx, row in df.iterrows():
    col0_val = str(row[0]).strip()
    
    # Check for the start of a block
    if col0_val.upper() == 'STATION':
        train_columns = {}
        # Scan across the row to find train numbers
        for col_idx in range(1, len(row)):
            val = str(row[col_idx]).strip()
            if val != 'nan' and val != '':
                # The train number is the first line of the cell
                train_num = val.split('\n')[0].strip()
                train_columns[col_idx] = train_num
        in_block = True
        continue
    
    # Skip overarching headers or empty rows
    if "CSMT- KALYAN" in col0_val or col0_val == 'nan' or col0_val == '':
        continue
        
    if in_block:
        station_name = col0_val
        unique_stations.add(station_name)
        
        # Extract times for each train found in the current block
        for col_idx, train_num in train_columns.items():
            time_val = str(row[col_idx]).strip()
            
            # Ignore empty cells, NaNs, and ellipses (which represent fast train skips)
            if time_val != 'nan' and time_val != '' and time_val != '…' and time_val != '...':
                
                # If pandas parsed it as a datetime.time object, it will cast to "00:02:00". 
                # We can normalize it slightly if needed, but for now we just capture it.
                if len(time_val.split(':')) == 3: # Handle HH:MM:SS
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
