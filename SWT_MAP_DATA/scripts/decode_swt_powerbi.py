import json, csv
from pathlib import Path
from collections import defaultdict

# 路径一律以脚本自身位置推导，不依赖终端当前工作目录
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
CURRENT_DIR = BASE_DIR / "current"

INPUT = RAW_DIR / "city_status_querydata.json"
OUTPUT = CURRENT_DIR / "swt_map_points.csv"

CURRENT_DIR.mkdir(parents=True, exist_ok=True)

with INPUT.open("r", encoding="utf-8") as f:
    data = json.load(f)

d = data["results"][0]["result"]["data"]
ds = d["dsr"]["DS"][0]
rows = ds["PH"][0]["DM0"]
value_dicts = ds["ValueDicts"]

fields = [x["N"] for x in rows[0]["S"]]
previous = [None] * len(fields)
records = []

for row in rows:
    cells = list(row.get("C", []))
    repeat_mask = row.get("R", 0)
    values, ci = [], 0

    for i in range(len(fields)):
        if repeat_mask & (1 << i):
            values.append(previous[i])
        else:
            values.append(cells[ci] if ci < len(cells) else None)
            if ci < len(cells):
                ci += 1

    previous = values
    state, city, status, lat, lon, participants = values

    if isinstance(state, int):
        state = value_dicts["D0"][state]
    if isinstance(city, int):
        city = value_dicts["D1"][city]
    if isinstance(status, int):
        status = value_dicts["D2"][status]

    records.append({
        "State": state,
        "City": city,
        "Status": status,
        "Latitude": lat,
        "Longitude": lon,
        "Participants": participants,
    })

with OUTPUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["State","City","Status","Latitude","Longitude","Participants"]
    )
    writer.writeheader()
    writer.writerows(records)

print(f"Decoded {len(records)} rows -> {OUTPUT}")
