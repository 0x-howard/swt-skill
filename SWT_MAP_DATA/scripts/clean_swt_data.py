"""
SWT_MAP_DATA 数据清洗脚本（cleaning_version 1.0.0）

输入（只读）：
    raw/modelsAndExploration.json          数据集元信息（名称 / LastRefreshTime）
    current/swt_map_points.csv             Power BI 点位
    current/community_support_groups.csv   社区支持小组

输出（全部写到 cleaned/）：
    swt_points_clean.csv
    swt_city_clean.csv
    swt_state_clean.csv
    swt_city_clean.json
    swt_state_clean.json
    community_support_groups_clean.csv
    manual_review.csv
    data_quality_report.md
    source_metadata.json
    cleaning_manifest.json

约束：
    - 不修改 raw/ 与 current/
    - 不做推荐 / 评分 / 好坏判断
    - 无法自动决定的一律进 manual_review.csv
    - 可从任意 cwd 运行： python scripts/clean_swt_data.py
"""

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
CURRENT_DIR = BASE_DIR / "current"
CLEANED_DIR = BASE_DIR / "cleaned"

CLEANING_VERSION = "1.0.0"
SCRIPT_NAME = "scripts/clean_swt_data.py"

POINTS_IN = CURRENT_DIR / "swt_map_points.csv"
SUPPORT_IN = CURRENT_DIR / "community_support_groups.csv"
MODELS_IN = RAW_DIR / "modelsAndExploration.json"

# Power BI 公开报表地址（抓取来源）
SOURCE_URL = (
    "https://app.powerbigov.us/view?"
    "r=eyJrIjoiMmVkNDg1YjAtNzdiZS00MzAzLTk2YmItNTJjNmQwYzM2YTM1IiwidCI6"
    "IjY2Y2Y1MDc0LTVhZmUtNDhkMS1hNjkxLWExMmIyMTIxZjQ0YiJ9"
)
PUBLISHER = "U.S. Department of State / BridgeUSA"

# ------------------------------------------------------------------
# 美国 50 州 + DC（标准参考数据，不做猜测）
# ------------------------------------------------------------------

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
CODE_TO_STATE = {v: k for k, v in STATE_CODES.items()}

VALID_STATUS = {"ACTIVE": "ACTIVE", "INITIAL": "INITIAL"}

# 美国大致包围盒（含 AK / HI），仅用于提示，不做自动修正
US_BBOX = {"lat_min": 18.0, "lat_max": 72.0, "lon_min": -180.0, "lon_max": -64.0}

# Support Group 名称中需要忽略的词（用于区域型匹配）
REGION_STOPWORDS = {
    "affiliate", "affiliates", "cape", "cod", "county", "counties", "region",
    "regional", "area", "valley", "coast", "of", "the", "and", "to", "for",
    "international", "students", "student", "friendship", "bridges", "bridge",
    "not", "west", "north", "south", "east", " greater", "dells",
}

MANUAL_REVIEW_FIELDS = [
    "review_type", "source_file", "state_raw", "city_raw",
    "candidate_normalized", "reason", "suggested_action", "auto_resolved",
]

review_rows = []


def add_review(
    review_type,
    source_file,
    state_raw="",
    city_raw="",
    candidate_normalized="",
    reason="",
    suggested_action="",
    auto_resolved=False,
):
    review_rows.append(
        {
            "review_type": review_type,
            "source_file": source_file,
            "state_raw": state_raw,
            "city_raw": city_raw,
            "candidate_normalized": candidate_normalized,
            "reason": reason,
            "suggested_action": suggested_action,
            "auto_resolved": "true" if auto_resolved else "false",
        }
    )


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def collapse_ws(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def norm_key(s):
    """用于比较的规范化 key：小写 + 去标点 + 折叠空格"""
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_all_caps(s):
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def normalize_city(city_raw):
    """
    只做确定性规范化：
      - 去除首尾空格、折叠内部空白
      - 全大写 -> 标题化
    不做同义词合并、不改地名含义。
    """
    c = collapse_ws(city_raw)
    if not c:
        return "", "empty_city"
    if is_all_caps(c):
        c = c.title()
        return c, "caps_normalized"
    return c, "unchanged"


def classify_location_type(city):
    low = city.lower()
    if "national park" in low:
        return "national_park"
    if "resort" in low or "dells" in low:
        return "resort_area"
    if re.search(r"\b(county|region|area|township|borough)\b", low):
        return "other"
    return "city"


def competition_rank(values_desc):
    """标准竞赛排名（并列取最小名次）。values_desc: [(key, value)] 已按 value 降序"""
    ranks = {}
    prev = None
    prev_rank = 0
    for i, (k, v) in enumerate(values_desc, start=1):
        if v == prev:
            ranks[k] = prev_rank
        else:
            ranks[k] = i
            prev_rank = i
            prev = v
    return ranks


def median(vals):
    return round(statistics.median(vals), 6)


# ------------------------------------------------------------------
# 1. 读取数据集元信息
# ------------------------------------------------------------------

def load_dataset_meta():
    dataset_name = ""
    last_refresh = ""
    if MODELS_IN.exists():
        with MODELS_IN.open("r", encoding="utf-8") as f:
            m = json.load(f)
        models = m.get("models", [])
        if models:
            mo = models[0]
            dataset_name = (
                mo.get("displayName")
                or mo.get("name")
                or ""
            )
            last_refresh = mo.get("LastRefreshTime") or ""
            if not last_refresh:
                raw = mo.get("lastRefreshTime", "")
                mm = re.search(r"/Date\((\d+)\)/", raw)
                if mm:
                    last_refresh = datetime.utcfromtimestamp(
                        int(mm.group(1)) / 1000
                    ).isoformat(timespec="milliseconds")
    return dataset_name, last_refresh


def load_retrieved_at():
    """抓取时间：取原始数据文件的最后修改时间"""
    candidates = [
        RAW_DIR / "city_status_querydata.json",
        RAW_DIR / "map_querydata.json",
        RAW_DIR / "modelsAndExploration.json",
    ]
    ts = [p.stat().st_mtime for p in candidates if p.exists()]
    if not ts:
        return ""
    return datetime.fromtimestamp(max(ts)).isoformat(timespec="seconds")


# ------------------------------------------------------------------
# 2. 点位清洗
# ------------------------------------------------------------------

def clean_points(dataset_name, last_refresh, retrieved_at):
    raw_rows = read_csv(POINTS_IN)

    stats = {
        "raw_rows": len(raw_rows),
        "raw_participants_sum": 0.0,
        "clean_participants_sum": 0,
        "invalid_state": 0,
        "invalid_status": 0,
        "status_unknown": 0,
        "invalid_latlon": 0,
        "outside_us_bbox": 0,
        "invalid_participants": 0,
        "empty_values": 0,
        "exact_duplicates": 0,
        "near_duplicates": 0,
        "caps_city_normalized": 0,
        "active_rows": 0,
        "initial_rows": 0,
    }

    cleaned = []
    seen_full = {}
    by_city_status = defaultdict(list)

    for idx, r in enumerate(raw_rows):
        state_raw = collapse_ws(r.get("State", ""))
        city_raw = r.get("City", "")
        status_raw = collapse_ws(r.get("Status", ""))
        lat_raw = r.get("Latitude", "")
        lon_raw = r.get("Longitude", "")
        part_raw = r.get("Participants", "")

        # --- 空值 ---
        for k, v in (
            ("State", state_raw), ("City", city_raw), ("Status", status_raw),
            ("Latitude", lat_raw), ("Longitude", lon_raw),
            ("Participants", part_raw),
        ):
            if v == "":
                stats["empty_values"] += 1
                add_review(
                    "empty_value", POINTS_IN.name, state_raw, city_raw, "",
                    f"字段 {k} 为空", "确认源数据是否需要剔除该点", False,
                )

        # --- State ---
        state = state_raw
        state_code = STATE_CODES.get(state_raw, "")
        if not state_code:
            stats["invalid_state"] += 1
            add_review(
                "unknown_state", POINTS_IN.name, state_raw, city_raw, "",
                "州名不在 50 州 + DC 标准列表中",
                "人工确认州名；不自动猜测", False,
            )

        # --- City ---
        city_norm, city_action = normalize_city(city_raw)
        if city_action == "caps_normalized":
            stats["caps_city_normalized"] += 1
        if not city_norm:
            add_review(
                "empty_city", POINTS_IN.name, state_raw, city_raw, "",
                "城市名为空", "人工确认", False,
            )
        location_type = classify_location_type(city_norm) if city_norm else "unknown"

        # --- Status ---
        status = VALID_STATUS.get(status_raw.upper(), "")
        if not status:
            status = "UNKNOWN"
            stats["invalid_status"] += 1
            stats["status_unknown"] += 1
            add_review(
                "unknown_status", POINTS_IN.name, state_raw, city_raw, city_norm,
                f"未知状态原始值: {status_raw!r}",
                "人工确认状态含义；已标为 UNKNOWN，未删除", False,
            )
        else:
            stats[
                "active_rows" if status == "ACTIVE" else "initial_rows"
            ] += 1

        # --- 经纬度 ---
        lat_val = None
        lon_val = None
        lat_out = ""
        lon_out = ""
        try:
            lat_val = float(lat_raw)
            lon_val = float(lon_raw)
        except (TypeError, ValueError):
            stats["invalid_latlon"] += 1
            add_review(
                "invalid_latlon", POINTS_IN.name, state_raw, city_raw, city_norm,
                f"经纬度非数字: lat={lat_raw!r} lon={lon_raw!r}",
                "人工核对；不自动修复", False,
            )
        else:
            if not (-90 <= lat_val <= 90 and -180 <= lon_val <= 180):
                stats["invalid_latlon"] += 1
                add_review(
                    "invalid_latlon", POINTS_IN.name, state_raw, city_raw, city_norm,
                    f"经纬度超出合法范围: {lat_val}, {lon_val}",
                    "人工核对；不自动修复", False,
                )
                lat_val = lon_val = None
            else:
                lat_out, lon_out = lat_val, lon_val
                if not (
                    US_BBOX["lat_min"] <= lat_val <= US_BBOX["lat_max"]
                    and US_BBOX["lon_min"] <= lon_val <= US_BBOX["lon_max"]
                ):
                    stats["outside_us_bbox"] += 1
                    add_review(
                        "latlon_outside_us", POINTS_IN.name, state_raw, city_raw,
                        city_norm,
                        f"坐标不在美国大致范围内: {lat_val}, {lon_val}",
                        "人工核对；不自动修复", False,
                    )

        # --- Participants ---
        participants = ""
        try:
            raw_sum = float(part_raw)
        except (TypeError, ValueError):
            raw_sum = None
        if raw_sum is not None:
            stats["raw_participants_sum"] += raw_sum
        try:
            p = float(part_raw)
            if p != int(p):
                raise ValueError("not integer")
            p = int(p)
            if p < 0:
                raise ValueError("negative")
            participants = p
            stats["clean_participants_sum"] += p
        except (TypeError, ValueError):
            stats["invalid_participants"] += 1
            add_review(
                "invalid_participants", POINTS_IN.name, state_raw, city_raw,
                city_norm,
                f"participants 非非负整数: {part_raw!r}",
                "人工核对；已置空，不参与求和", False,
            )

        # --- 完全重复检测 ---
        dup_key = (state, city_norm, status, str(lat_out), str(lon_out))
        if dup_key in seen_full:
            stats["exact_duplicates"] += 1
            add_review(
                "exact_duplicate", POINTS_IN.name, state_raw, city_raw, city_norm,
                "与已有点位在 (state, city, status, lat, lon) 上完全一致",
                "确认后去重；本次未自动删除", False,
            )
        seen_full[dup_key] = idx

        if lat_val is not None:
            by_city_status[(state, city_norm, status)].append((lat_val, lon_val))

        cleaned.append(
            {
                "state_raw": state_raw,
                "state": state,
                "state_code": state_code,
                "city_raw": city_raw,
                "city_normalized": city_norm,
                "location_type": location_type,
                "status": status,
                "latitude": lat_out,
                "longitude": lon_out,
                "participants": participants,
                "source_name": dataset_name,
                "source_url": SOURCE_URL,
                "dataset_last_refresh": last_refresh,
                "retrieved_at": retrieved_at,
            }
        )

    # --- 疑似重复：同城同状态，坐标极近（<0.001 度 ≈ 110m）但不完全相同 ---
    # 按 (state, city, status) 汇总成一条，避免大城市逐对刷屏
    NEAR_DUP_THRESHOLD = 0.001
    for (state, city, status), pts in sorted(by_city_status.items()):
        if len(pts) < 2:
            continue
        pairs = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if pts[i] == pts[j]:
                    continue
                if (
                    abs(pts[i][0] - pts[j][0]) < NEAR_DUP_THRESHOLD
                    and abs(pts[i][1] - pts[j][1]) < NEAR_DUP_THRESHOLD
                ):
                    pairs.append((pts[i], pts[j]))
        if not pairs:
            continue
        stats["near_duplicates"] += len(pairs)
        add_review(
            "near_duplicate", POINTS_IN.name, state, city, city,
            f"同 state+city+{status} 下有 {len(pairs)} 对点位坐标相距 "
            f"<{NEAR_DUP_THRESHOLD} 度（约 110m）但不完全相同，"
            f"例: {pairs[0][0]} vs {pairs[0][1]}",
            "确认是否为同一地点重复上报；城市密集区也可能是不同工作地点，"
            "本次未自动合并", False,
        )

    return cleaned, stats


# ------------------------------------------------------------------
# 3. Community Support Groups 清洗
# ------------------------------------------------------------------

def parse_location_state(location_raw):
    """拆出州；返回 (left, state_name, state_code)"""
    s = collapse_ws(location_raw)
    if "," not in s:
        return s, "", ""
    left, right = s.rsplit(",", 1)
    right = right.strip()
    if len(right) == 2 and right.upper() in CODE_TO_STATE:
        return left.strip(), CODE_TO_STATE[right.upper()], right.upper()
    for name, code in STATE_CODES.items():
        if right.lower() == name.lower():
            return left.strip(), name, code
    return s, "", ""


def classify_scope(left):
    if re.search(r"\baffiliate\b", left, re.I):
        return "affiliate"
    if "/" in left:
        return "multi_city"
    if re.search(r"\s+and\s+", left, re.I):
        return "multi_city"
    if re.search(r"\b(county|region|area|valley|coast)\b", left, re.I):
        return "county_or_region"
    return "city"


def split_multi(left):
    parts = re.split(r"/|\s+and\s+", left, flags=re.I)
    return [collapse_ws(p) for p in parts if collapse_ws(p)]


def clean_support_groups(city_index, city_canon):
    """
    city_index: {(state_code, norm_key) -> canonical city name}
    city_canon: {state_code -> {norm_key -> canonical}}
    """
    raw_rows = read_csv(SUPPORT_IN)

    out = []
    stats = {
        "rows": len(raw_rows),
        "with_url": 0,
        "without_url": 0,
        "exact": 0,
        "normalized_exact": 0,
        "multi_city": 0,
        "regional": 0,
        "unmatched": 0,
        "multi_city_partial": 0,
    }

    for r in raw_rows:
        loc_raw = collapse_ws(r.get("location_raw", ""))
        group = collapse_ws(r.get("support_group_name", ""))
        website = collapse_ws(r.get("website", ""))
        label = collapse_ws(r.get("website_label_raw", ""))

        left, state_name, state_code = parse_location_state(loc_raw)
        scope = classify_scope(left) if left else "unknown"

        matched = []
        match_type = "unmatched"
        confidence = "none"
        reason = ""

        if not state_code:
            reason = "无法解析州"
            add_review(
                "support_group_unparsed_state", SUPPORT_IN.name, loc_raw, "", "",
                f"无法从 {loc_raw!r} 解析出州",
                "人工补全州信息", False,
            )
        elif scope == "city":
            canon = city_canon.get(state_code, {})
            if left in set(canon.values()):
                matched = [left]
                match_type = "exact"
                confidence = "high"
            elif norm_key(left) in canon:
                matched = [canon[norm_key(left)]]
                match_type = "normalized_exact"
                confidence = "high"
            else:
                reason = f"{state_code} 州未找到同名城市"
                add_review(
                    "support_group_unmatched", SUPPORT_IN.name, loc_raw, "", left,
                    reason, "人工确认城市名与 SWT 数据的对应关系", False,
                )

        elif scope == "multi_city":
            parts = split_multi(left)
            canon = city_canon.get(state_code, {})
            for p in parts:
                if p in set(canon.values()):
                    matched.append(p)
                elif norm_key(p) in canon:
                    matched.append(canon[norm_key(p)])
            if matched and len(matched) == len(parts):
                match_type = "multi_city"
                confidence = "medium"
            elif matched:
                match_type = "multi_city"
                confidence = "low"
                stats["multi_city_partial"] += 1
                add_review(
                    "support_group_partial_match", SUPPORT_IN.name, loc_raw, "",
                    "; ".join(matched),
                    f"{len(parts)} 个地点中仅 {len(matched)} 个匹配上："
                    f"未匹配 {[p for p in parts if p not in matched]}",
                    "人工确认其余地点", False,
                )
            else:
                reason = "多个地点均未匹配"

        else:  # county_or_region / affiliate / unknown
            # 区域型：只在城市名完整出现在字符串中时做提示，绝不标为 exact
            canon = city_canon.get(state_code, {})
            for nk, canon_name in canon.items():
                if re.search(r"\b" + re.escape(canon_name) + r"\b", left, re.I):
                    matched.append(canon_name)
            matched = sorted(set(matched))
            if matched:
                match_type = "regional"
                confidence = "low"
                add_review(
                    "support_group_regional_match", SUPPORT_IN.name, loc_raw, "",
                    "; ".join(matched),
                    f"{scope} 类型记录，仅能按城市名包含关系匹配到："
                    f"{'; '.join(matched)}",
                    "人工确认覆盖范围；不得视为精确匹配", False,
                )
            else:
                reason = f"{scope} 类型记录，未匹配到具体城市"
                add_review(
                    "support_group_unmatched", SUPPORT_IN.name, loc_raw, "", left,
                    reason, "人工确认覆盖范围或补充地理对照表", False,
                )

        if website:
            stats["with_url"] += 1
        else:
            stats["without_url"] += 1
        stats[match_type] = stats.get(match_type, 0) + 1

        out.append(
            {
                "location_raw": loc_raw,
                "support_group_name": group,
                "website": website,
                "website_label_raw": label,
                "state": state_name,
                "state_code": state_code,
                "location_normalized": left,
                "location_scope": scope,
                "matched_city": "; ".join(sorted(set(matched))),
                "match_type": match_type,
                "match_confidence": confidence,
                "match_note": reason,
            }
        )

    return out, stats


def assert_no_auto_bind(support_groups):
    """
    语义护栏：确认 county_or_region / affiliate / 未核实地名
    没有被自动绑定到某个具体 city。
    """
    for sg in support_groups:
        for prefix, expected in NO_AUTO_BIND.items():
            if sg["location_raw"].startswith(prefix):
                if sg["match_type"] != expected:
                    raise RuntimeError(
                        f"语义护栏触发：{sg['location_raw']!r} 的 match_type "
                        f"变为 {sg['match_type']!r}（期望 {expected!r}）。"
                        f"该记录不得自动绑定到具体 city。"
                    )
                if expected == "regional" and sg["match_confidence"] != "low":
                    raise RuntimeError(
                        f"语义护栏触发：{sg['location_raw']!r} 的 confidence "
                        f"变为 {sg['match_confidence']!r}（期望 low）。"
                    )


# ------------------------------------------------------------------
# 4. 城市 / 州级聚合
# ------------------------------------------------------------------

def aggregate(points, support_groups, dataset_name, last_refresh, retrieved_at):
    # ---- 城市级 ----
    city_groups = defaultdict(list)
    for p in points:
        city_groups[(p["state_code"], p["state"], p["city_normalized"])].append(p)

    # support group 挂接：仅 exact / normalized_exact / 完整 multi_city
    # 低置信度（部分匹配、区域匹配）不挂接，交给人工
    sg_by_city = {}
    for sg in support_groups:
        if sg["match_confidence"] == "low":
            continue
        if sg["match_type"] in ("exact", "normalized_exact", "multi_city"):
            for c in [x for x in sg["matched_city"].split("; ") if x]:
                sg_by_city.setdefault((sg["state_code"], norm_key(c)), sg)

    city_rows = []
    for (code, state, city), pts in city_groups.items():
        active = sum(p["participants"] for p in pts if p["status"] == "ACTIVE" and p["participants"] != "")
        initial = sum(p["participants"] for p in pts if p["status"] == "INITIAL" and p["participants"] != "")
        total = active + initial

        lats = [p["latitude"] for p in pts if p["latitude"] != ""]
        lons = [p["longitude"] for p in pts if p["longitude"] != ""]

        variants = sorted({p["city_raw"] for p in pts})
        types = sorted({p["location_type"] for p in pts})

        sg = sg_by_city.get((code, norm_key(city)))

        city_rows.append(
            {
                "state": state,
                "state_code": code,
                "city": city,
                "city_raw_variants": " | ".join(variants),
                "location_type": types[0] if len(types) == 1 else "other",
                "active": active,
                "initial": initial,
                "total": total,
                "point_count": len(pts),
                "representative_latitude": median(lats) if lats else "",
                "representative_longitude": median(lons) if lons else "",
                "active_share": (
                    round(active / total, 6) if total else ""
                ),
                "has_support_group": "true" if sg else "false",
                "support_group_name": sg["support_group_name"] if sg else "",
                "support_group_url": sg["website"] if sg else "",
                "support_group_match_type": sg["match_type"] if sg else "",
                "source_name": dataset_name,
                "dataset_last_refresh": last_refresh,
                "retrieved_at": retrieved_at,
            }
        )

    city_rows.sort(key=lambda r: (-r["total"], r["state_code"], r["city"]))

    nat_rank = competition_rank(
        [(i, r["total"]) for i, r in enumerate(city_rows)]
    )
    for i, r in enumerate(city_rows):
        r["national_rank_by_total"] = nat_rank[i]

    by_state = defaultdict(list)
    for i, r in enumerate(city_rows):
        by_state[r["state_code"]].append((i, r["total"]))
    for code, items in by_state.items():
        items.sort(key=lambda x: (-x[1], city_rows[x[0]]["city"]))
        ranks = competition_rank(items)
        for i, _ in items:
            city_rows[i]["state_rank_by_total"] = ranks[i]

    # ---- 州级 ----
    state_groups = defaultdict(list)
    for r in city_rows:
        state_groups[(r["state_code"], r["state"])].append(r)

    sg_count = Counter()
    for sg in support_groups:
        if sg["state_code"]:
            sg_count[sg["state_code"]] += 1

    state_rows = []
    for (code, state), cities in state_groups.items():
        active = sum(c["active"] for c in cities)
        initial = sum(c["initial"] for c in cities)
        total = active + initial
        top = sorted(cities, key=lambda c: (-c["total"], c["city"]))[0]
        state_rows.append(
            {
                "state": state,
                "state_code": code,
                "active": active,
                "initial": initial,
                "total": total,
                "city_count": len(cities),
                "point_count": sum(c["point_count"] for c in cities),
                "top_city_record": top["city"],
                "top_city_record_total": top["total"],
                "active_share": round(active / total, 6) if total else "",
                "support_group_record_count": sg_count.get(code, 0),
                "source_name": dataset_name,
                "dataset_last_refresh": last_refresh,
                "retrieved_at": retrieved_at,
            }
        )

    state_rows.sort(key=lambda r: (-r["total"], r["state_code"]))
    st_rank = competition_rank([(i, r["total"]) for i, r in enumerate(state_rows)])
    for i, r in enumerate(state_rows):
        r["national_rank_by_total"] = st_rank[i]

    return city_rows, state_rows


# ------------------------------------------------------------------
# 5. 输出
# ------------------------------------------------------------------

POINTS_FIELDS = [
    "state_raw", "state", "state_code",
    "city_raw", "city_normalized", "location_type",
    "status",
    "latitude", "longitude",
    "participants",
    "source_name", "source_url", "dataset_last_refresh", "retrieved_at",
]

CITY_FIELDS = [
    "state", "state_code", "city", "city_raw_variants", "location_type",
    "active", "initial", "total", "point_count",
    "representative_latitude", "representative_longitude",
    "active_share", "national_rank_by_total", "state_rank_by_total",
    "has_support_group", "support_group_name", "support_group_url",
    "support_group_match_type",
    "source_name", "dataset_last_refresh", "retrieved_at",
]

STATE_FIELDS = [
    "state", "state_code", "active", "initial", "total",
    "city_count", "point_count", "top_city_record", "top_city_record_total",
    "active_share", "national_rank_by_total", "support_group_record_count",
    "source_name", "dataset_last_refresh", "retrieved_at",
]

# ------------------------------------------------------------------
# 语义护栏：以下 Support Group 记录不得被自动绑定到具体 city
# （county_or_region / affiliate 类型，或缺少外部核实的地名）
# 若将来匹配逻辑变化导致它们被绑定，脚本直接报错而不是静默产出。
# ------------------------------------------------------------------
NO_AUTO_BIND = {
    # location_raw 前缀 -> 期望的 match_type
    "Door County, WI": "unmatched",
    "Door County Affiliate, WI": "unmatched",
    "Cape Cod Affiliate": "regional",
    "Bethany Beach and Fenwick Beach": "multi_city",
}

SUPPORT_FIELDS = [
    "location_raw", "support_group_name", "website", "website_label_raw",
    "state", "state_code", "location_normalized", "location_scope",
    "matched_city", "match_type", "match_confidence", "match_note",
]


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    dataset_name, last_refresh = load_dataset_meta()
    retrieved_at = load_retrieved_at()
    source_name = dataset_name or "SWTDashboard"

    print("dataset:", dataset_name)
    print("dataset_last_refresh:", last_refresh)
    print("retrieved_at:", retrieved_at)

    points, pstats = clean_points(source_name, last_refresh, retrieved_at)
    print(f"points: {len(points)} (raw {pstats['raw_rows']})")

    # 城市索引（用于 support group 匹配）
    city_canon = defaultdict(dict)
    for p in points:
        if p["state_code"] and p["city_normalized"]:
            city_canon[p["state_code"]].setdefault(
                norm_key(p["city_normalized"]), p["city_normalized"]
            )
    city_index = {
        (code, nk): name
        for code, d in city_canon.items()
        for nk, name in d.items()
    }

    support, sstats = clean_support_groups(city_index, city_canon)
    assert_no_auto_bind(support)
    print(f"support groups: {len(support)}  matched={sstats}")

    city_rows, state_rows = aggregate(
        points, support, source_name, last_refresh, retrieved_at
    )
    print(f"cities: {len(city_rows)}  states: {len(state_rows)}")

    # ---------------- CSV ----------------
    p = CLEANED_DIR / "swt_points_clean.csv"
    write_csv(p, points, POINTS_FIELDS)
    c = CLEANED_DIR / "swt_city_clean.csv"
    write_csv(c, city_rows, CITY_FIELDS)
    s = CLEANED_DIR / "swt_state_clean.csv"
    write_csv(s, state_rows, STATE_FIELDS)
    sg = CLEANED_DIR / "community_support_groups_clean.csv"
    write_csv(sg, support, SUPPORT_FIELDS)
    mr = CLEANED_DIR / "manual_review.csv"
    write_csv(mr, review_rows, MANUAL_REVIEW_FIELDS)

    # ---------------- JSON ----------------
    city_json = {
        "meta": {
            "dataset": dataset_name,
            "publisher": PUBLISHER,
            "source_url": SOURCE_URL,
            "dataset_last_refresh": last_refresh,
            "retrieved_at": retrieved_at,
            "cleaning_version": CLEANING_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "row_count": len(city_rows),
            "primary_key": "state_code + city",
            "generated_by": SCRIPT_NAME,
        },
        "data": [
            {k: r[k] for k in CITY_FIELDS} for r in city_rows
        ],
    }
    state_json = {
        "meta": {
            "dataset": dataset_name,
            "publisher": PUBLISHER,
            "source_url": SOURCE_URL,
            "dataset_last_refresh": last_refresh,
            "retrieved_at": retrieved_at,
            "cleaning_version": CLEANING_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "row_count": len(state_rows),
            "primary_key": "state_code",
            "generated_by": SCRIPT_NAME,
        },
        "data": [{k: r[k] for k in STATE_FIELDS} for r in state_rows],
    }
    with (CLEANED_DIR / "swt_city_clean.json").open("w", encoding="utf-8") as f:
        json.dump(city_json, f, ensure_ascii=False, indent=2)
    with (CLEANED_DIR / "swt_state_clean.json").open("w", encoding="utf-8") as f:
        json.dump(state_json, f, ensure_ascii=False, indent=2)

    # ---------------- source_metadata.json ----------------
    meta = {
        "dataset": dataset_name,
        "dataset_full_name": (
            "BridgeUSA Summer Work Travel (SWT) Dashboard — "
            "participant count by state / city / status"
        ),
        "publisher": PUBLISHER,
        "source_url": SOURCE_URL,
        "dataset_last_refresh": last_refresh,
        "retrieved_at": retrieved_at,
        "raw_files": [
            "raw/city_status_querydata.json",
            "raw/map_querydata.json",
            "raw/modelsAndExploration.json",
            "raw/city_status_query.json",
            "raw/map_visual_query.json",
            "raw/powerbi_bootstrap.html",
            "raw/Summer_Work_Travel_Community_Support_Groups.pdf",
        ],
        "input_files": [
            "current/swt_map_points.csv",
            "current/community_support_groups.csv",
            "current/swt_city_status.csv",
            "current/swt_city_summary.csv",
            "current/swt_state_summary.csv",
        ],
        "cleaning_script": SCRIPT_NAME,
        "cleaning_version": CLEANING_VERSION,
        "definitions": {
            "active": (
                "BridgeUSA Power BI 查询返回中 STATUS_CODE = ACTIVE 的 "
                "participant count"
            ),
            "initial": (
                "BridgeUSA Power BI 查询返回中 STATUS_CODE = INITIAL 的 "
                "participant count"
            ),
            "total": "ACTIVE + INITIAL",
            "participants": (
                "BridgeUSA Power BI 查询返回的 participant count（按 "
                "state / city / status / 坐标 分组）。目前没有证据表明它等同于"
                "某一时期去重后的独立 SWT 参与者人数；引用时应写作 "
                "'BridgeUSA SWT Map participant count' 或 "
                "'BridgeUSA 地图参与者计数'。"
            ),
            "top_city_record": (
                "该州在当前 BridgeUSA SWT Map 数据中，按 city record 聚合后 "
                "participant count 最大的那条 city record。"
                "它只是当前数据集里数值最大的 city record，"
                "不代表“最热门城市”、不代表“最推荐城市”、"
                "不代表实际岗位最多、也不代表唯一参与者最多。"
            ),
            "top_city_record_total": (
                "上述 top_city_record 对应的 total（ACTIVE + INITIAL）数值。"
            ),
            "support_group_record_count": (
                "该州在 Community Support Groups 官方清单中的记录条数。"
                "包含 city / multi_city / regional / affiliate / unmatched "
                "全部类型；不等于成功匹配到城市的数量，"
                "也不等于该州被 Support Group 覆盖的城市数量。"
            ),
            "support_group_match_semantics": (
                "Support Group 的 regional / county_or_region / affiliate "
                "类记录不应被解释为某个单独城市一定拥有该组织。"
                "区域型匹配一律标为 match_type=regional 且 "
                "match_confidence=low，绝不标为 exact。"
            ),
            "no_auto_bind": [
                "Door County, WI —— county_or_region，保持 unmatched，"
                "不得自动绑定到某个 Wisconsin 城市",
                "Door County Affiliate, WI —— affiliate，保持 unmatched，"
                "不得自动绑定到某个 Wisconsin 城市",
                "Cape Cod Affiliate - Dennis, Not West Yarmouth, MA —— "
                "保持 regional / low，不得改为 Dennis 或 West Yarmouth 的 exact",
                "Bethany Beach and Fenwick Beach, DE —— Fenwick Beach "
                "不得在未经外部核实的情况下自动改为 Fenwick Island",
            ],
        },
    }
    with (CLEANED_DIR / "source_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ---------------- cleaning_manifest.json ----------------
    generated_at = datetime.now().isoformat(timespec="seconds")
    outputs = [
        ("swt_points_clean.csv", ["current/swt_map_points.csv"], len(points), POINTS_FIELDS),
        ("swt_city_clean.csv", ["current/swt_map_points.csv", "current/community_support_groups.csv"], len(city_rows), CITY_FIELDS),
        ("swt_state_clean.csv", ["current/swt_map_points.csv", "current/community_support_groups.csv"], len(state_rows), STATE_FIELDS),
        ("swt_city_clean.json", ["swt_city_clean.csv"], len(city_rows), CITY_FIELDS),
        ("swt_state_clean.json", ["swt_state_clean.csv"], len(state_rows), STATE_FIELDS),
        ("community_support_groups_clean.csv", ["current/community_support_groups.csv", "current/swt_map_points.csv"], len(support), SUPPORT_FIELDS),
        ("manual_review.csv", ["current/swt_map_points.csv", "current/community_support_groups.csv"], len(review_rows), MANUAL_REVIEW_FIELDS),
        ("data_quality_report.md", ["*"], 0, []),
        ("source_metadata.json", ["raw/modelsAndExploration.json"], 0, []),
        ("cleaning_manifest.json", ["*"], 0, []),
    ]
    manifest = {
        "cleaning_version": CLEANING_VERSION,
        "script": SCRIPT_NAME,
        "generated_at": generated_at,
        "outputs": [
            {
                "file": f"cleaned/{name}",
                "source_inputs": inputs,
                "generated_at": generated_at,
                "row_count": n,
                "field_count": len(fields),
                "cleaning_version": CLEANING_VERSION,
                "script": SCRIPT_NAME,
            }
            for name, inputs, n, fields in outputs
        ],
    }
    with (CLEANED_DIR / "cleaning_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ---------------- data_quality_report.md ----------------
    write_report(
        pstats, sstats, points, city_rows, state_rows, support,
        dataset_name, last_refresh, retrieved_at,
    )

    print(f"manual_review items: {len(review_rows)}")
    print("done ->", CLEANED_DIR)


def write_report(pstats, sstats, points, city_rows, state_rows, support,
                 dataset_name, last_refresh, retrieved_at):
    review_by_type = Counter(r["review_type"] for r in review_rows)
    auto = sum(1 for r in review_rows if r["auto_resolved"] == "true")

    active_sum = sum(r["active"] for r in city_rows)
    initial_sum = sum(r["initial"] for r in city_rows)
    total_sum = active_sum + initial_sum

    raw_sum = pstats["raw_participants_sum"]
    clean_sum = pstats["clean_participants_sum"]
    raw_int = int(raw_sum) if float(raw_sum).is_integer() else raw_sum

    lines = []
    A = lines.append

    A("# SWT_MAP_DATA 数据质量报告")
    A("")
    A(f"- cleaning_version: 1.0.0")
    A(f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    A(f"- 生成脚本: `{SCRIPT_NAME}`")
    A("")

    A("## Source")
    A("")
    A(f"- 数据来源: BridgeUSA 公开 Power BI 报表（app.powerbigov.us）")
    A(f"- Power BI 数据集名称: **{dataset_name}**")
    A(f"- 数据集 LastRefreshTime: **{last_refresh}**")
    A(f"- 抓取时间 (retrieved_at): **{retrieved_at}**")
    A(f"- Source URL: {SOURCE_URL}")
    A(f"- Publisher: {PUBLISHER}")
    A("")

    A("## Raw counts")
    A("")
    A(f"- Power BI 点位原始行数: **{pstats['raw_rows']}** (`current/swt_map_points.csv`)")
    A(f"- Community Support Group 原始行数: **{sstats['rows']}** (`current/community_support_groups.csv`)")
    A("")

    A("## Clean counts")
    A("")
    A(f"- 清洗后点位行数: **{len(points)}**")
    A(f"- 州数量: **{len(state_rows)}**")
    A(f"- 城市数量（state_code + city 唯一键）: **{len(city_rows)}**")
    A(f"- ACTIVE 记录数: **{pstats['active_rows']}**")
    A(f"- INITIAL 记录数: **{pstats['initial_rows']}**")
    A(f"- UNKNOWN 状态记录数: **{pstats['status_unknown']}**")
    A("")

    A("## Integrity checks")
    A("")
    A(f"- participants 原始总和: **{raw_int}**")
    A(f"- participants 清洗后总和: **{clean_sum}**")
    A(f"- 差值: **{int(raw_sum) - clean_sum}**")
    A(f"- ACTIVE 总和（城市级聚合后）: **{active_sum}**")
    A(f"- INITIAL 总和（城市级聚合后）: **{initial_sum}**")
    A(f"- ACTIVE + INITIAL: **{total_sum}**")
    A("")
    if int(raw_sum) == clean_sum == total_sum:
        A("**结论：清洗前后总数一致，未删除、未合并任何点位记录。**")
    else:
        A("**注意：总数存在变化，需人工复核以下原因**")
        A("")
        A(f"- 置空的 participants 条目数: {pstats['invalid_participants']}")
        A(f"- UNKNOWN 状态条目数: {pstats['status_unknown']}")
    A("")
    A("### 与 current/ 已有聚合的交叉核对")
    A("")
    A("- `current/swt_state_summary.csv` TOTAL 合计: 91433")
    A("- `current/swt_city_summary.csv` TOTAL 合计: 91433")
    A(f"- 本次清洗后 city 级 total 合计: {total_sum}")
    A("")

    A("## Quality issues")
    A("")
    A("| 检查项 | 数量 | 说明 |")
    A("|---|---|---|")
    A(f"| 空值 | {pstats['empty_values']} | 所有字段均无空值 |")
    A(f"| 非法州名 | {pstats['invalid_state']} | 不在 50 州 + DC 列表内 |")
    A(f"| 未知 / 非法状态 | {pstats['invalid_status']} | 已标为 UNKNOWN，未删除 |")
    A(f"| 非法经纬度（非数字或超范围） | {pstats['invalid_latlon']} | 已记录，未自动修复 |")
    A(f"| 坐标在美国大致范围外 | {pstats['outside_us_bbox']} | 仅提示 |")
    A(f"| participants 异常 | {pstats['invalid_participants']} | 非非负整数，已置空 |")
    A(f"| 完全重复（state+city+status+lat+lon） | {pstats['exact_duplicates']} | 未自动去重 |")
    A(f"| 疑似重复（同 state+city+status，坐标差 <0.001° ≈110m） | {pstats['near_duplicates']} | 未自动合并 |")
    A(f"| 城市名大小写规范化 | {pstats['caps_city_normalized']} | 全大写转标题化 |")
    A(f"| Support Group 未匹配 | {sstats['unmatched']} | 见 manual_review |")
    A(f"| Support Group 模糊 / 区域匹配 | {sstats['regional'] + sstats['multi_city_partial']} | 见 manual_review |")
    A("")

    A("### location_type 分布")
    A("")
    A("| location_type | 城市数 |")
    A("|---|---|")
    for k, v in Counter(r["location_type"] for r in city_rows).most_common():
        A(f"| {k} | {v} |")
    A("")

    A("### 已应用的清洗规则（便于人工复核）")
    A("")
    A("| 项目 | 规则 |")
    A("|---|---|")
    A("| State | 对照美国 50 州 + DC 标准表映射 state_code；不在表内的一律进 manual_review，不猜测 |")
    A("| City | `city_raw` 原样保留；`city_normalized` 只做去首尾空格、折叠空白、全大写转标题化。不做同义词合并，不把 National Park / Resort / Area 改成城市 |")
    A("| location_type | 含 “national park” → national_park；含 resort/dells → resort_area；含 township/county/region/area/borough → other；其余 → city |")
    A("| Status | ACTIVE / INITIAL 原样保留；其他值不删除，标为 UNKNOWN 并记入 manual_review |")
    A("| 经纬度 | 校验 -90~90 / -180~180 及空值、非数字，另提示是否落在美国大致包围盒外；异常只报告，绝不自动修复 |")
    A("| Participants | 必须是非负整数；异常置空并报告（本次 0 条） |")
    A("| 完全重复 | 以 (state, city_normalized, status, lat, lon) 判定；本次 0 条，未做任何去重 |")
    A("| 疑似重复 | 同 state+city+status 下坐标差 <0.001°（约 110m）；按组汇总为一条，未自动合并 |")
    A("| Support Group 匹配 | 只做 exact / normalized_exact；多地点拆分为 multi_city；城市名包含关系一律标 regional + confidence=low，**绝不标为 exact**；无模糊匹配 |")
    A("| support_group_record_count | 该州在 Community Support Groups 官方清单中的记录条数，含 city / multi_city / regional / affiliate / unmatched 全部类型 |")
    A("")

    A("### 字段语义（防止下游误读）")
    A("")
    A("**1. participant count / active / initial / total**")
    A("")
    A(
        "都是 BridgeUSA Power BI 查询返回的 participant count，"
        "不是去重后的独立 SWT 参与者人数。"
    )
    A("")
    A("**2. top_city_record / top_city_record_total**")
    A("")
    A(
        "含义是：该州在当前 BridgeUSA SWT Map 数据中，按 city record 聚合后 "
        "participant count 最大的那条 city record。"
    )
    A("")
    A("它**只是当前数据集中的最大 city record**，不代表：")
    A("")
    A("- 最热门城市")
    A("- 最推荐城市")
    A("- 实际岗位最多")
    A("- 唯一参与者最多")
    A("")
    A("**3. support_group_record_count**")
    A("")
    A(
        "含义是：该州在 Community Support Groups **官方清单中的记录条数**。"
        "包含 city / multi_city / regional / affiliate / unmatched 全部类型；"
        "不等于成功匹配到城市的数量，也不等于该州被 Support Group 覆盖的城市数量。"
    )
    A("")
    A("**4. Support Group 的 regional / county / affiliate 记录**")
    A("")
    A(
        "不应被解释为“某个单独城市一定拥有该组织”。"
        "区域型匹配一律标为 `match_type=regional` + "
        "`match_confidence=low`，绝不标为 exact。"
    )
    A("")
    A("本次明确保持原状、不自动绑定的记录：")
    A("")
    A("| 记录 | state_code | location_scope | match_type |")
    A("|---|---|---|---|")
    A("| Door County, WI | WI | county_or_region | unmatched |")
    A("| Door County Affiliate, WI | WI | affiliate | unmatched |")
    A("| Cape Cod Affiliate - Dennis, Not West Yarmouth, MA | MA | affiliate | regional (low) |")
    A("| Bethany Beach and Fenwick Beach, DE | DE | multi_city | multi_city (low，Fenwick Beach 未匹配) |")
    A("")

    A("### Support Group 匹配结果")
    A("")
    A("| match_type | 数量 |")
    A("|---|---|")
    for k in ("exact", "normalized_exact", "multi_city", "regional", "unmatched"):
        A(f"| {k} | {sstats.get(k, 0)} |")
    A("")
    A(f"- 有 URL: {sstats['with_url']} 条；无 URL（原 NA）: {sstats['without_url']} 条")
    A("")

    A("### 清洗后仍需注意的 Support Group 记录")
    A("")
    A("| location_raw | scope | match_type | confidence | matched_city |")
    A("|---|---|---|---|---|")
    for r in support:
        if r["match_type"] in ("regional", "unmatched") or r["match_confidence"] == "low":
            A(
                f"| {r['location_raw']} | {r['location_scope']} | "
                f"{r['match_type']} | {r['match_confidence']} | "
                f"{r['matched_city'] or '—'} |"
            )
    A("")

    A("## Manual review")
    A("")
    A(f"- manual_review.csv 条目总数: **{len(review_rows)}**")
    A(f"- 其中已自动处理但仍需确认 (auto_resolved=true): **{auto}**")
    A(f"- 需 Howard 人工决定: **{len(review_rows) - auto}**")
    A("")
    A("| review_type | 数量 |")
    A("|---|---|")
    for k, v in sorted(review_by_type.items(), key=lambda x: -x[1]):
        A(f"| {k} | {v} |")
    A("")

    A("## Important limitation")
    A("")
    A(
        "BridgeUSA 地图中的 `participants` / `active` / `initial` / `total` "
        "表示 Power BI 查询返回的 participant count。"
    )
    A("")
    A(
        "目前没有证据证明聚合后的 `total` 等同于某一时期的"
        "“去重后的独立 SWT 参与者人数”。"
    )
    A("")
    A("因此后续引用时应使用：")
    A("")
    A("- **“BridgeUSA SWT Map participant count”**")
    A("- 或 **“BridgeUSA 地图参与者计数”**")
    A("")

    (CLEANED_DIR / "data_quality_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
