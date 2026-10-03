import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_EXCEL = DATA / "raw_excel"
EXTRACTED = DATA / "extracted"
GTFS = DATA / "gtfs"
STATION_MAPPING = DATA / "station_mapping.json"


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
