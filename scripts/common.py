from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_EXCEL = DATA / "raw_excel"
EXTRACTED = DATA / "extracted"
GTFS = DATA / "gtfs"
STATION_MAPPING = DATA / "station_mapping.json"
