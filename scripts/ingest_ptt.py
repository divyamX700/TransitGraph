"""Public Time Table (PTT) Excel -> data/extracted/<source>.csv with columns train_number,station,time.

Each sheet is a series of blocks: a header row (first cell "STATION...", one
train per column) followed by one row per station. Faithful extraction only;
merging trains across files and mapping station names happen in compile_gtfs.py.
"""
import re

import pandas as pd

from common import EXTRACTED, RAW_EXCEL

SOURCES = {
    "central_dn": "1728294831372-SUB PTT DN ML'24.xlsx",
    "central_up": "1728294891897-SUB PTT UP ML'24.xlsx",
    "harbour_dn": "1777550323377-DN HB REVISED PTT WEF 01.05.2026.xlsx",
    "harbour_up": "1777550366723-UP HB REVISED PTT WEF 01.05.2026.xlsx",
    "western_dn": "1777701123504-DN PTT W.E.F. 01.05.2026.xlsx",
    "western_up": "1777701192855-UP PTT W.E.F 01.05.2026.xlsx",
    "western_dahanu": "1777728749169-PTT 78 FOR DAHANU ROAD SERVICES W.E.F. 01.05.2026.xlsx",
    "port_line": "1781160975368-PORT LINE PTT WEF 15.12.2025.xlsx",
    "trans_harbour": "1781174782507-THB PTT wef 13.01.2024.xlsx",
}

TRAIN_NO = re.compile(r"\b(\d{5}[A-Z]?)\b")
TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?")
HEADER_CELLS = ("TR.NO", "TRAIN NO")
# Cells that are not stations: merged blocks, titles that leaked in.
NOT_A_STATION = ("LADIES ONLY", "TIME TABLE", "W.E.F", "TRAINS")


def is_header(cell):
    u = cell.upper()
    return u.startswith("STATION") or any(h in u for h in HEADER_CELLS)


def is_station(cell):
    if cell in ("", "nan") or (len(cell) > 30 and "\n" in cell):
        return False
    return not any(t in cell.upper() for t in NOT_A_STATION)


def train_numbers(df, row, col):
    r"""Train number(s) for a column. Usually the header cell is "DRD 93001\n12 CAR". One
    Central cell holds two trains side by side ("95802      97202"). On later pages of the
    Western sheets the header holds only a destination code ("VR") and the number sits in
    one of the next rows, so look down the column too."""
    found = TRAIN_NO.findall(str(df.iat[row, col]).split("\n")[0])
    if found:
        return found
    for r in range(row + 1, min(row + 4, len(df))):
        m = TRAIN_NO.fullmatch(str(df.iat[r, col]).strip())
        if m:
            return [m[1]]
    return []


def to_hhmm(cell):
    """'5:12', '05:12:00', or Excel float noise like '05:51:59.962000' (really 05:52)."""
    m = TIME.fullmatch(cell)
    if not m:
        return None
    mins = int(m[1]) * 60 + int(m[2]) + round(float(m[3] or 0) / 60)
    return f"{mins // 60 % 24:02d}:{mins % 60:02d}"


def ingest(name, filename):
    df = pd.read_excel(RAW_EXCEL / filename, header=None)
    rows, rejected, no_number = [], [], 0
    columns = {}
    for i in range(len(df)):
        first = str(df.iat[i, 0]).strip()
        if is_header(first):
            columns = {}
            for c in range(1, df.shape[1]):
                if str(df.iat[i, c]).strip() in ("nan", ""):
                    continue
                nums = train_numbers(df, i, c)
                if nums:
                    columns[c] = nums
                else:
                    no_number += 1
            continue
        if not columns or not is_station(first):
            continue
        for c, nums in columns.items():
            cell = str(df.iat[i, c]).strip()
            parts = cell.split() if len(nums) > 1 else [cell]
            if len(parts) != len(nums):
                parts = [cell] * len(nums)  # unreadable for every train in the column
            for num, part in zip(nums, parts):
                hhmm = to_hhmm(part)
                if hhmm:
                    rows.append((num, " ".join(first.split()), hhmm))
                elif re.search(r"\d", part):
                    rejected.append((num, first, cell))
    out = pd.DataFrame(rows, columns=["train_number", "station", "time"])
    out.to_csv(EXTRACTED / f"{name}.csv", index=False)
    print(f"{name}: {len(out)} stop times, {out.train_number.nunique()} trains"
          f", {no_number} header columns without a train number")
    for r in rejected:
        print(f"  unreadable time cell: train {r[0]}, {r[1]!r}: {r[2]!r}")


if __name__ == "__main__":
    EXTRACTED.mkdir(exist_ok=True)
    for name, filename in SOURCES.items():
        ingest(name, filename)
