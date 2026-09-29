# SWT_MAP_DATA 数据质量报告

- cleaning_version: 1.0.0
- 生成时间: 2026-09-26T16:16:32
- 生成脚本: `scripts/clean_swt_data.py`

## Source

- 数据来源: BridgeUSA 公开 Power BI 报表（app.powerbigov.us）
- Power BI 数据集名称: **SWTDashboard**
- 数据集 LastRefreshTime: **2026-07-20T19:41:07.883**
- 抓取时间 (retrieved_at): **2026-09-26T15:01:52**
- Source URL: https://app.powerbigov.us/view?r=eyJrIjoiMmVkNDg1YjAtNzdiZS00MzAzLTk2YmItNTJjNmQwYzM2YTM1IiwidCI6IjY2Y2Y1MDc0LTVhZmUtNDhkMS1hNjkxLWExMmIyMTIxZjQ0YiJ9
- Publisher: U.S. Department of State / BridgeUSA

## Raw counts

- Power BI 点位原始行数: **3649** (`current/swt_map_points.csv`)
- Community Support Group 原始行数: **15** (`current/community_support_groups.csv`)

## Clean counts

- 清洗后点位行数: **3649**
- 州数量: **51**
- 城市数量（state_code + city 唯一键）: **2465**
- ACTIVE 记录数: **3006**
- INITIAL 记录数: **643**
- UNKNOWN 状态记录数: **0**

## Integrity checks

- participants 原始总和: **91433**
- participants 清洗后总和: **91433**
- 差值: **0**
- ACTIVE 总和（城市级聚合后）: **87679**
- INITIAL 总和（城市级聚合后）: **3754**
- ACTIVE + INITIAL: **91433**

**结论：清洗前后总数一致，未删除、未合并任何点位记录。**

### 与 current/ 已有聚合的交叉核对

- `current/swt_state_summary.csv` TOTAL 合计: 91433
- `current/swt_city_summary.csv` TOTAL 合计: 91433
- 本次清洗后 city 级 total 合计: 91433

## Quality issues

| 检查项 | 数量 | 说明 |
|---|---|---|
| 空值 | 0 | 所有字段均无空值 |
| 非法州名 | 0 | 不在 50 州 + DC 列表内 |
| 未知 / 非法状态 | 0 | 已标为 UNKNOWN，未删除 |
| 非法经纬度（非数字或超范围） | 0 | 已记录，未自动修复 |
| 坐标在美国大致范围外 | 0 | 仅提示 |
| participants 异常 | 0 | 非非负整数，已置空 |
| 完全重复（state+city+status+lat+lon） | 0 | 未自动去重 |
| 疑似重复（同 state+city+status，坐标差 <0.001° ≈110m） | 0 | 未自动合并 |
| 城市名大小写规范化 | 0 | 全大写转标题化 |
| Support Group 未匹配 | 2 | 见 manual_review |
| Support Group 模糊 / 区域匹配 | 2 | 见 manual_review |

### location_type 分布

| location_type | 城市数 |
|---|---|
| city | 2454 |
| other | 6 |
| national_park | 4 |
| resort_area | 1 |

### 已应用的清洗规则（便于人工复核）

| 项目 | 规则 |
|---|---|
| State | 对照美国 50 州 + DC 标准表映射 state_code；不在表内的一律进 manual_review，不猜测 |
| City | `city_raw` 原样保留；`city_normalized` 只做去首尾空格、折叠空白、全大写转标题化。不做同义词合并，不把 National Park / Resort / Area 改成城市 |
| location_type | 含 “national park” → national_park；含 resort/dells → resort_area；含 township/county/region/area/borough → other；其余 → city |
| Status | ACTIVE / INITIAL 原样保留；其他值不删除，标为 UNKNOWN 并记入 manual_review |
| 经纬度 | 校验 -90~90 / -180~180 及空值、非数字，另提示是否落在美国大致包围盒外；异常只报告，绝不自动修复 |
| Participants | 必须是非负整数；异常置空并报告（本次 0 条） |
| 完全重复 | 以 (state, city_normalized, status, lat, lon) 判定；本次 0 条，未做任何去重 |
| 疑似重复 | 同 state+city+status 下坐标差 <0.001°（约 110m）；按组汇总为一条，未自动合并 |
| Support Group 匹配 | 只做 exact / normalized_exact；多地点拆分为 multi_city；城市名包含关系一律标 regional + confidence=low，**绝不标为 exact**；无模糊匹配 |
| support_group_record_count | 该州在 Community Support Groups 官方清单中的记录条数，含 city / multi_city / regional / affiliate / unmatched 全部类型 |

### 字段语义（防止下游误读）

**1. participant count / active / initial / total**

都是 BridgeUSA Power BI 查询返回的 participant count，不是去重后的独立 SWT 参与者人数。

**2. top_city_record / top_city_record_total**

含义是：该州在当前 BridgeUSA SWT Map 数据中，按 city record 聚合后 participant count 最大的那条 city record。

它**只是当前数据集中的最大 city record**，不代表：

- 最热门城市
- 最推荐城市
- 实际岗位最多
- 唯一参与者最多

**3. support_group_record_count**

含义是：该州在 Community Support Groups **官方清单中的记录条数**。包含 city / multi_city / regional / affiliate / unmatched 全部类型；不等于成功匹配到城市的数量，也不等于该州被 Support Group 覆盖的城市数量。

**4. Support Group 的 regional / county / affiliate 记录**

不应被解释为“某个单独城市一定拥有该组织”。区域型匹配一律标为 `match_type=regional` + `match_confidence=low`，绝不标为 exact。

本次明确保持原状、不自动绑定的记录：

| 记录 | state_code | location_scope | match_type |
|---|---|---|---|
| Door County, WI | WI | county_or_region | unmatched |
| Door County Affiliate, WI | WI | affiliate | unmatched |
| Cape Cod Affiliate - Dennis, Not West Yarmouth, MA | MA | affiliate | regional (low) |
| Bethany Beach and Fenwick Beach, DE | DE | multi_city | multi_city (low，Fenwick Beach 未匹配) |

### Support Group 匹配结果

| match_type | 数量 |
|---|---|
| exact | 10 |
| normalized_exact | 0 |
| multi_city | 2 |
| regional | 1 |
| unmatched | 2 |

- 有 URL: 12 条；无 URL（原 NA）: 3 条

### 清洗后仍需注意的 Support Group 记录

| location_raw | scope | match_type | confidence | matched_city |
|---|---|---|---|---|
| Bethany Beach and Fenwick Beach, DE | multi_city | multi_city | low | Bethany Beach |
| Cape Cod Affiliate - Dennis, Not West Yarmouth, MA | affiliate | regional | low | Dennis; West Yarmouth |
| Door County, WI | county_or_region | unmatched | none | — |
| Door County Affiliate, WI | affiliate | unmatched | none | — |

## Manual review

- manual_review.csv 条目总数: **4**
- 其中已自动处理但仍需确认 (auto_resolved=true): **0**
- 需 Howard 人工决定: **4**

| review_type | 数量 |
|---|---|
| support_group_unmatched | 2 |
| support_group_partial_match | 1 |
| support_group_regional_match | 1 |

## Important limitation

BridgeUSA 地图中的 `participants` / `active` / `initial` / `total` 表示 Power BI 查询返回的 participant count。

目前没有证据证明聚合后的 `total` 等同于某一时期的“去重后的独立 SWT 参与者人数”。

因此后续引用时应使用：

- **“BridgeUSA SWT Map participant count”**
- 或 **“BridgeUSA 地图参与者计数”**

