# SWT Skill Changelog

## v0.8.0 — SWT English Practice

- 在 v0.7 English Assessment 基础上增加场景化口语训练闭环，通过 Assessment Result 自动选择弱项，支持 Agency、Sponsor、Host 和 Visa 四类 Practice、动态追问、短反馈、Retry 和 Reassessment。
- 为四类 Practice 复用既有 Assessment Profile 与 question-bank；增加 FULL MOCK、WEAKNESS DRILL、FOLLOW-UP DRILL、QUESTION DRILL 和 SCENARIO DRILL，不新增 Skill、题库、Rubric 或 Assessment Result Schema。
- 增加独立的最小 `english_practice` 状态；按最高影响问题给短反馈、鼓励用户自行重答，记录 before／after 改善但不覆盖正式 Assessment。
- 更新 English 路由、v0.8 行为验收场景、README、plugin manifests 和生成的 shared runtime 版本标记。

## v0.7.0 — SWT English Assessment

- Added `ASSESS` to the existing `swt-english` Skill: four generic scenario profiles plus a one-session Comprehensive Assessment, using one shared seven-criterion evidence set.
- Added actionable seven-dimension scoring anchors, evidence/confidence/input-mode rules, adaptive question types, compact first-result output, fact-conflict handling for Visa communication, and IELTS-style estimates with explicit non-official limits.
- Added deterministic profile Readiness weighting in `scripts/speaking_score.py`; missing or undersampled criteria produce a partial result.
- Kept the existing six-Skill plugin layout and the prior English interview, correction, follow-up, and general SWT communication capabilities.

## v0.6 — SWT Market / Location Data Layer

Recorded from the current project files and source artifacts; no earlier release log was used to infer unimplemented features.

- Added the `swt_market` reference layer generated from `SWT_MAP_DATA/cleaned/`, containing BridgeUSA map state/city aggregates and Community Support Group records, with indexes, source metadata, and methodology.
- Current cleaned artifacts report 51 state rows, 2,465 city rows, and 15 Community Support Group records. The associated quality report records 3,649 retained map point rows, matching participant-count totals before and after cleaning, and four Support Group entries retained for manual review.
- Added source-specific limits for interpreting participant counts and matching regional, affiliate, and multi-city support records; these are background context, not offer recommendations or unique annual participant counts.
- Added data cleaning/build scripts and connected the resulting state and market context to the existing SWT specialist workflows.

## v0.5 — Decision Output & Budget Model

- Added a six-dimension position comparison output, after-tax break-even / project balance calculations, labeled default estimates for missing ordinary budget inputs, and progressive detail expansion.
- Added tax-mode distinctions and warnings for planning estimates, missing data, and Sponsor approval boundaries.

## v0.4 — State-first Position

- Added state-level SWT context and location resolution, state reference material, and reusable position budget inputs to support state-aware comparisons.

## v0.3 — Six-Skill Architecture

- Established the six existing Skills: `swt`, `swt-application`, `swt-position`, `swt-english`, `swt-visa`, and `swt-arrival`, with routing and specialist boundaries.

## v0.2 — Position Prototype

Reconstructed from development history; original Codex logs incomplete.

- Began structuring position choice as a distinct module, providing a base for the later `swt-position` Skill.

## v0.1 — Personal Experience Prototype

Reconstructed from development history; original Codex logs incomplete.

- Organized Howard's early SWT application, position selection, interview, arrival, and work experience into the initial SWT Skill.
