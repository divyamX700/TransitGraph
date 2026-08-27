# Data Sources Reference

## Official Timetable PDFs

The raw timetable data for Phase 1 (Mumbai Local) is located in `data/raw_pdfs/`. The mapping and parsing logic is as follows:

### Central Line (Main Line)
- `1728294831372-SUB PTT DN ML'24.pdf`: CSMT to Kasara (Down)
- `1728294891897-SUB PTT UP ML'24.pdf`: Kasara to CSMT (Up)

### Harbour Line
- `1777550323377-DN HB REVISED PTT WEF 01.05.2026.pdf`: CSMT to Panvel / CSMT to Goregaon (Down). 
  - *Engineering Note: Contains diverging branches that share initial stations.*
- `1777550366723-UP HB REVISED PTT WEF 01.05.2026.pdf`: Panvel/Goregaon to CSMT (Up).

### Western Line
- `1777701123504-DN PTT W.E.F. 01.05.2026.pdf`: Churchgate to Virar (Down)
- `1777701192855-UP PTT W.E.F 01.05.2026.pdf`: Virar to Churchgate (Up)
- `1777728749169-PTT 78 FOR DAHANU ROAD SERVICES W.E.F. 01.05.2026.pdf`: Churchgate to Dahanu Road (Both Up and Down). 
  - *Engineering Note: Trains in this file overlap with the main Western Line files but contain the extended route. De-duplicate based on Train Number, treating this file as the source of truth.*

### Trans Harbour Line
- `1781174782507-THB PTT wef 13.01.2024.pdf`: Thane to Vashi/Panvel.

### Port Line
- `1781160975368-PORT LINE PTT WEF 15.12.2025.pdf`: Nerul/Belapur to Uran (Both Up and Down).

## Geographical Data
- Station names, Latitude, Longitude, and track geometries (for `shapes.txt`) will be sourced externally via **OpenStreetMap (OSM)** to ensure geographical accuracy for the frontend map visualization.
