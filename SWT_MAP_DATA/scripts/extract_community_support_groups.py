"""
把 raw/Summer_Work_Travel_Community_Support_Groups.pdf 中的
CITY, STATE / COMMUNITY SUPPORT GROUPS / WEBSITES 三列表格
忠实导出为 current/community_support_groups.csv。

原则：
- 不做清洗、不拆 city/state、不改拼写
- PDF 里的 "NA" 写成空值
- website 保留完整 URL（来自 PDF 的链接注释）
"""

import base64
import csv
import re
import zlib
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
CURRENT_DIR = BASE_DIR / "current"

PDF = RAW_DIR / "Summer_Work_Travel_Community_Support_Groups.pdf"
OUTPUT = CURRENT_DIR / "community_support_groups.csv"

# 表格外层位移（来自 PDF 内容流 "1 0 0 1 51.35433 159.1906 cm"）
OUTER_X = 51.35433
OUTER_Y = 159.1906

# 三列的相对 x
COL_X = {"location": 6.0, "group": 167.5748, "website": 388.6772}

LINE_HEIGHT = 9.2  # 表格正文 "9.2 TL"


def load_content_stream() -> str:
    raw = PDF.read_bytes()
    m = re.search(rb"stream\r?\n(.*?)endstream", raw, re.S)
    return zlib.decompress(base64.a85decode(m.group(1).strip(), adobe=True)).decode(
        "latin-1"
    )


def parse_text_items(txt: str):
    """返回 [(baseline_y, x, text)]，baseline_y 为页面绝对坐标。"""
    items = []

    # 每个单元格块： 1 0 0 1 <x> <y> cm ... BT 1 0 0 1 0 <ty> Tm /Fn <size> Tf <lh> TL (..) Tj T* (..) Tj ... ET
    block_re = re.compile(
        r"1 0 0 1 ([-\d.]+) ([-\d.]+) cm"
        r"[\s\S]*?"
        r"1 0 0 1 0 ([-\d.]+) Tm\s*/F\d ([\d.]+) Tf"
        r"[\s\S]*?ET"
    )

    for blk in block_re.finditer(txt):
        cx, cy, ty = float(blk.group(1)), float(blk.group(2)), float(blk.group(3))
        body = blk.group(0)

        strings = re.findall(r"\((.*?)\) Tj", body)
        if not strings:
            continue

        base = OUTER_Y + cy + ty
        for i, s in enumerate(strings):
            s = s.replace(r"\(", "(").replace(r"\)", ")")
            items.append((base - i * LINE_HEIGHT, round(OUTER_X + cx, 1), s, i))

    return items


def parse_links():
    """返回 [(rect_y0, uri)]，rect_y0 为页面绝对坐标。"""
    raw = PDF.read_text("latin-1")
    out = []
    for a in re.finditer(
        r"/URI \(([^)]*)\)\s*>>\s*/Border\s*\[[^\]]*\]\s*/Rect\s*\[\s*"
        r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]",
        raw,
    ):
        uri, _x0, y0, _x1, _y1 = a.groups()
        out.append((float(y0), uri))
    return out


def main():
    txt = load_content_stream()
    items = parse_text_items(txt)
    links = parse_links()

    # 行锚点 = location 列每个文本块的基线（每行有且仅有一个 location 单元格）
    loc_x = OUTER_X + COL_X["location"]
    anchors = sorted(
        {
            round(y, 1)
            for y, x, _s, line_idx in items
            if abs(x - loc_x) < 1.0 and line_idx == 0
        },
        reverse=True,
    )

    ROW_PITCH = 19.2  # 表格行距

    def row_of(y):
        """文本落在哪一行：从锚点向下 19.2 范围内都属于该行（含换行续行）。"""
        for a in anchors:
            if a - ROW_PITCH + 0.5 < y <= a + 0.5:
                return a
        return None

    rows = defaultdict(lambda: defaultdict(list))
    for y, x, s, _li in items:
        r = row_of(y)
        if r is None:
            continue  # 标题 / 表头 / 页脚
        for col, colx in COL_X.items():
            if abs(x - (OUTER_X + colx)) < 1.0:
                rows[r][col].append(s)

    def nearest_link(y):
        best, bestd = None, None
        for ly, uri in links:
            d = abs((y - 0.91) - ly)  # 链接下划线 rect 位于基线下约 0.91
            if bestd is None or d < bestd:
                best, bestd = uri, d
        return best if bestd is not None and bestd < 3 else ""

    records = []
    for r in anchors:
        cells = rows.get(r, {})

        loc = " ".join(cells.get("location", [])).strip()
        group = " ".join(cells.get("group", [])).strip()
        site_text = " ".join(cells.get("website", [])).strip()

        # PDF 中明确写 NA 的，输出为空值
        if site_text.upper() == "NA":
            site_text = ""
        if loc.upper() == "NA":
            loc = ""

        records.append(
            {
                "location_raw": loc,
                "support_group_name": group,
                "website": nearest_link(r),
                "website_label_raw": site_text,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "location_raw",
                "support_group_name",
                "website",
                "website_label_raw",
            ],
        )
        w.writeheader()
        w.writerows(records)

    print(f"rows: {len(records)} -> {OUTPUT}")
    for i, r in enumerate(records, 1):
        print(
            f"{i:2d} | {r['location_raw']} | {r['support_group_name']} "
            f"| {r['website']} | ({r['website_label_raw']})"
        )


if __name__ == "__main__":
    main()
