# Summary

- total cases: 20
- passed: 20
- failed: 0
- pass rate: 100.0%

- existing unit/integration regression: 105 passed before Eval and 105 passed after Eval
- E2E unittest checks: 22 passed (20 case checks plus fixture/report checks)

## Eval scope and limitation

本轮验证总路由 Skill 中的路由契约、真实 Location Context 结果、州／市场事实及现有预算计算器输出。仓库没有可调用的实时模型／路由运行器，因此没有执行模型新生成的自然语言回答。`no_overclaim`、表述方式和重复度按可观测的确定性输出及 Skill 约束核对；若要验收真实回答措辞，还需另做实时模型评测。

## Scores by dimension

| Dimension | PASS | FAIL |
|---|---:|---:|
| `route_correct` | 20 | 0 |
| `location_correct` | 20 | 0 |
| `facts_correct` | 20 | 0 |
| `no_hallucination` | 20 | 0 |
| `no_overclaim` | 20 | 0 |
| `structure_preserved` | 20 | 0 |
| `no_redundancy` | 20 | 0 |

## Case results (deterministic contract validation)

| Case | Route | Location | Facts | No hallucination | No overclaim | Structure | No redundancy | Result |
|---|---|---|---|---|---|---|---|---|
| `market_001` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_002` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_003` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_004` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_005` | PASS | PASS (A: city_exact, B: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_006` | PASS | PASS (A: city_exact, B: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_007` | PASS | PASS (A: city_exact, B: state_fallback) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_008` | PASS | PASS (CITY: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_009` | PASS | PASS (A: city_exact, B: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_010` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_011` | PASS | PASS (Ocean: city_exact, Myrtle: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_012` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_013` | PASS | PASS (A: state_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_014` | PASS | PASS (A: state_fallback) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `market_015` | PASS | PASS (A: city_exact) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `route_016` | PASS | PASS (not resolved by design) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `route_017` | PASS | PASS (not resolved by design) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `route_018` | PASS | PASS (not resolved by design) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `route_019` | PASS | PASS (not resolved by design) | PASS | PASS | PASS | PASS | PASS | **PASS** |
| `ambiguous_020` | PASS | PASS (not resolved by design) | PASS | PASS | PASS | PASS | PASS | **PASS** |

# Failures

## P0

None.

## P1

None.

## P2

None.

## P3

None.

# Required location case details

## Myrtle Beach (`market_001`)

- user_query: 我拿到 Myrtle Beach, SC 的 Offer：$15/h，40h/week，housing $150/week，工作 12 周，帮我完整分析。
- route: `swt-position`
- location_match: `{'A': 'city_exact'}`
- resolved_facts: `{"A": {"city_exact_support": ["Myrtle Beach ISOP"], "city_total": 2050, "match_level": "city_exact", "regional_support": [], "state_context_available": true, "state_total": 2852, "support_level": "city_exact", "swt_market_available": true}}`
- score: **PASS**
- evidence note: 核对 city_exact、州级背景、Market 数据和完整 Offer 概览结构。

## Ocean City (`market_002`)

- user_query: Ocean City, MD 的完整 Offer：$17/h，40h/week，住宿 $160/week，工作 12 周。
- route: `swt-position`
- location_match: `{'A': 'city_exact'}`
- resolved_facts: `{"A": {"city_exact_support": ["Ocean City Summer Work Travel Committee"], "city_total": 3693, "match_level": "city_exact", "regional_support": [], "state_context_available": true, "state_total": 5918, "support_level": "city_exact", "swt_market_available": true}}`
- score: **PASS**
- evidence note: 核对 Ocean City, MD 的城市、州和 Support 记录未串用其他城市数据。

## Rhode Island (`market_004`)

- user_query: 我在 Newport, Rhode Island 有一份 $16/h、35h/week、住宿 $175/week、12 周的 Offer，请完整分析。
- route: `swt-position`
- location_match: `{'A': 'city_exact'}`
- resolved_facts: `{"A": {"city_exact_support": [], "city_total": 430, "match_level": "city_exact", "regional_support": [], "state_context_available": false, "state_total": 1030, "support_level": "none", "swt_market_available": true}}`
- score: **PASS**
- evidence note: Market 可用、州级 knowledge layer 缺失时仍继续计算；不填造州税或最低工资。

## Fenwick Beach (`market_007`)

- user_query: 比较 Myrtle Beach, SC 和 Fenwick Beach, DE 的 Offer。
- route: `swt-position`
- location_match: `{'A': 'city_exact', 'B': 'state_fallback'}`
- resolved_facts: `{"A": {"city_exact_support": ["Myrtle Beach ISOP"], "city_total": 2050, "match_level": "city_exact", "regional_support": [], "state_context_available": true, "state_total": 2852, "support_level": "city_exact", "swt_market_available": true}, "B": {"city_exact_support": [], "city_total": null, "match_level": "state_fallback", "regional_support": [{"location_raw": "Bethany Beach and Fenwick Beach, DE", "location_scope": "multi_city", "match_type": "multi_city"}], "state_context_available": true, "state_total": 1791, "support_level": "regional_evidence", "swt_market_available": true}}`
- score: **PASS**
- evidence note: 一个 city_exact、一个 state_fallback；DE 区域支持不得改成城市精确支持。

## Door County (`market_015`)

- user_query: Door County 有 Community Support Group 吗？
- route: `swt-position`
- location_match: `{'A': 'city_exact'}`
- resolved_facts: `{"A": {"city_exact_support": [], "city_total": null, "match_level": "city_exact", "regional_support": [{"location_raw": "Door County, WI", "location_scope": "county_or_region", "match_type": "unmatched"}], "state_context_available": true, "state_total": 5478, "support_level": "regional_evidence", "swt_market_available": true}}`
- score: **PASS**
- evidence note: 额外核对 Cape Cod Affiliate 区域证据见 diagnostic_locations；不增加用户场景数。
- Support 解释：地点 identity 返回 `city_exact`，但 `city_market` 为空；Support 仍是 `county_or_region` / `unmatched`，不代表城市精确匹配。

## Cape Cod regional-support diagnostic

- location_match: `city_exact`
- support evidence: `[{"location_raw": "Cape Cod Affiliate - Dennis, Not West Yarmouth, MA", "location_scope": "affiliate", "match_type": "regional"}]`
- 解释：Dennis 本身解析为城市，但 Support 记录是 affiliate／区域证据，匹配置信度低；不能表述为该城市存在精确匹配的 Community Support Group。

# Engineering quality result

这是工程行为契约评分，不是 Offer 或地点评分。本轮只新增 Eval 测试、fixture 和报告，没有修改任何 Skill、Resolver、脚本或源数据。
