# SWT Skill

> 面向美国 Summer Work Travel 学生的 AI 决策、测评与流程辅助工具。

**Current Version: v0.8.0**

[GitHub 源码仓库](https://github.com/0x-howard/swt-skill)

SWT Skill 将 Summer Work Travel 从报名、选岗、英语面试、签证到赴美后的常见问题，整理成一套可复用的 Skills、业务资料、计算工具和交互规则。它不替用户做决定，而是帮助用户降低搜集与筛选信息的成本，用统一框架比较岗位和地点，估算收入、生活成本与回本情况，并在 SWT 各阶段提供结构化辅助。

它可以帮助用户：

- 比较岗位与地点，检查 Offer 中会影响选择的条件。
- 根据已知信息估算收入、生活成本、项目结余和回本时间。
- 完成 SWT 场景化英语测评与口语训练。
- 梳理申请、签证、入境和在美期间的问题与下一步。

## What can it do?

### 1. SWT 全流程导航 — `swt`

根据用户当前问题、项目阶段、风险和已知上下文，路由到对应专项 Skill，覆盖：

`报名 → 申请 → 选岗 → 英语面试 → 签证 → 行前 → 入境 → 在美工作与生活 → 项目结束`

已知信息会在当前对话中复用，不重复询问。

### 2. 报名与申请 — `swt-application`

- SWT 资格与申请流程
- Agency／Sponsor、报名、合同与付款
- Resume、Video、Application Materials
- Sponsor 系统、Employer Application 与申请阶段问题排查

### 3. 岗位与 Offer 分析 — `swt-position`

围绕“岗位＋地点＋住宿＋通勤＋项目日期”分析 Offer，关注六个维度：

| 维度 | 主要内容 |
|---|---|
| 收入 | 时薪、平均工时与预计收入 |
| 住宿 | 房租与住宿条件 |
| 生活成本 | 餐饮与必要生活支出 |
| 交通 | 通勤方式、成本与便利度 |
| 二工 | 第二份工作的现实条件与审批边界 |
| 落地便利 | SSN、银行与基础生活设施等 |

默认先给一句结论，再给六维核心数据表、回本测算、注意事项和一个继续选择题。用户只提供时薪与平均每周工时，也可以先估算；普通缺项按“岗位真实值 → 城市参考 → 州级参考 → SWT 通用默认值”补齐，并将估算标为“估”。

预算模型可呈现税前工资、预计税费、住宿、餐饮、交通和其他必要生活成本、在美净结余、SWT 前期投入、最终预计结余及回本所需工作周数。预计税费和默认生活成本是规划估算，不是最终税单或 Offer 条款。确定性计算主要由 `scripts/budget.py` 完成，不依赖语言模型自行心算。

### 4. SWT English — `swt-english`

英语能力分为四个入口：

| 入口 | 用途 |
|---|---|
| `ASSESS` | 测量当前 SWT 场景英语准备度，形成正式 Assessment Result。 |
| `PRACTICE` | 按测评弱项或用户选择的场景练习，经过短反馈、Retry 和 Reassessment。 |
| `INTERVIEW` | 模拟 Sponsor、Host Employer 或 Visa 面试官进行角色练习。 |
| `GENERAL ENGLISH` | 练工作沟通、日常英语、口语纠错与一般表达。 |

**English Assessment — v0.7** 支持 Agency Screening、Sponsor Screening、Host Employer Interview、Visa Interview Communication 和 Comprehensive Assessment。所有 Profile 共用七维能力，但按场景采用不同权重：

1. 理解与切题
2. 流利与连贯
3. 词汇表达
4. 语法控制
5. 发音可理解度
6. 互动与修复
7. 任务沟通

Agency 更关注基础口语和基本交流；Sponsor 更关注理解、互动、追问与实际沟通；Host 根据具体岗位评价工作沟通；Visa 关注听懂问题、直接作答、表达清楚并如实沟通。Assessment 还可提供 IELTS-style Speaking Estimate：它只参考 IELTS Speaking 公开维度，不代表官方 IELTS 成绩。没有真实音频证据时，不会假装评价发音。

**English Practice — v0.8** 将 Assessment Result 转化为训练闭环：

`ASSESS → DIAGNOSE → PRACTICE → RETRY → REASSESS`

支持 Agency、Sponsor、Host 和 Visa Interview Practice，以及 Weakness、Follow-up、Question、Scenario Drill 和 Full Mock。已有 v0.7 测评结果时，优先训练 `top_weaknesses` 中最重要的 1–2 项；没有测评结果时，也可以直接选择场景或指定弱项开始。每题先回答，再接收短反馈并 Retry，之后进入追问或下一题。默认提供提示、关键词或句型骨架，不直接给一整篇背诵答案，训练用户自己表达。

### 5. Visa — `swt-visa`

辅助核对 DS-2019、DS-160、I-901 SEVIS Fee、签证预约、面签准备，以及文件间事实是否一致。职责边界是：

- `swt-visa`：事实、材料、流程与信息一致性。
- `swt-english`：如何清楚表达已经核实的真实信息。

如果面试回答与已有材料冲突，优先核实事实；不会帮助用户把错误事实表达得更自然或更可信。

### 6. Arrival & U.S. Life — `swt-arrival`

覆盖行前准备、美国入境、I-94、Sponsor Check-in、SSN、保险、工作与住宿问题、二工审批、项目结束与返程。

## How to use

在已添加 `personal` marketplace 的 Codex 环境中安装：

```bash
codex plugin add swt-plugin@personal
```

安装或更新后开启新 conversation，让 Codex 重新发现 Skills。之后用自然语言描述当前任务即可，例如“帮我比较这两个 Offer”“按上次测评的弱项陪我练口语”或“核对 DS-2019 和 DS-160 的信息是否一致”。

## SWT Market & Location Context

项目包含州级 SWT Context、城市与地点解析、州税参考，以及 BridgeUSA SWT Map 和 Community Support Groups 的市场背景资料。完整岗位分析会按地点解析结果加载适用的州／城市 Context：

`Offer → 地点解析 → 城市／州 Context → 岗位分析`

这些资料用于补充判断，不替代具体 Offer、雇主、住宿地址和排班等真实条件。BridgeUSA participant count 不等同于年度去重参与者人数；市场计数或 Support Group 记录本身也不能证明某地更容易找到工作或二工。

## Interaction Design

### Choice First

优先使用选择题，其次是是／否题、结构化填写，最后才是开放题，以减少用户组织答案的成本。

### Progressive Disclosure

`FIRST RESPONSE = OVERVIEW`；`FOLLOW-UP = DETAIL`。后台可以读取较多资料，但首答只呈现理解结论和采取下一步所需的信息；用户追问后再展开细节。

### Reuse Known Context

已知信息会在当前对话中复用。例如用户已提供岗位和工时，之后说“如果每周只有 28 小时呢？”，只更新 `weekly_hours` 并重算受影响的项目。

## Project Structure

```text
swt-skill/
├── .codex-plugin/
├── skills/
│   ├── swt/
│   ├── swt-application/
│   ├── swt-position/
│   ├── swt-english/
│   ├── swt-visa/
│   └── swt-arrival/
├── shared/
├── references/
│   ├── knowledge/
│   └── shared-runtime/
├── SWT_MAP_DATA/
├── scripts/
├── assets/
└── tests/
    ├── unit/
    ├── integration/
    └── evals/
```

- `skills/`：六个 Skill 的入口和专项指引。
- `shared/`：跨 Skill 行为规则的 Single Source of Truth。
- `references/`：SWT 业务知识、地点数据、英语评分资料与默认值。
- `scripts/`：确定性计算、同步、校验与维护工具。
- `assets/`：示例输入和静态素材。
- `tests/`：unit、integration 和 behavior eval。
- `SWT_MAP_DATA/`：SWT 地图资料的原始、清理与生成数据。

## Source of Truth

共享规则只在 `shared/` 维护，再通过 `scripts/sync_shared.py` 生成到 `references/shared-runtime/`：

`shared/ → scripts/sync_shared.py → references/shared-runtime/`

`shared-runtime/` 是生成文件，不直接编辑。岗位默认估算值集中维护于 `references/default-assumptions.json`。English Assessment 的 Rubric、Profile、题型与流程分别维护在对应的 English reference 中；不要在 `SKILL.md` 或多个文件中复制评分标准。

## Development

以下命令从插件根目录运行：

```bash
python3 scripts/sync_shared.py
python3 scripts/sync_shared.py --check
python3 scripts/validate.py

python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/integration -v
python3 tests/test_plugin.py

python3 scripts/rebuild.py
python3 scripts/clean.py --cache
```

## Current Status

**Version: v0.8.0**

当前能力可以概括为：

`SWT Knowledge + Position Decision + Budget Calculation + Location Context + English Assessment + English Practice + Visa & Arrival Support`

自动测试不能完全代表真实 Runtime 对话体验。v0.8 完成后的重点验证是在新 conversation 中联合检查 `ASSESS → PRACTICE → RETRY → REASSESS` 的实际表现。

## Author

SWT Skill — Howard  
@哎哟不想上早八啊（全平台同名）

# Version History

| Version | Main Update | What changed |
|---|---|---|
| v0.1 | Personal Experience Prototype | 根据 Howard 自身 SWT 申请、选岗、面试、赴美和工作经历建立第一版 SWT Skill 原型。 |
| v0.2 | Position Prototype | 开始把岗位选择独立结构化，形成后续 `swt-position` 的原型。 |
| v0.3 | Six-Skill Architecture | 建立 `swt`、`swt-application`、`swt-position`、`swt-english`、`swt-visa`、`swt-arrival` 六 Skill 架构和共享规则体系。 |
| v0.4 | State-first Position | 增加州级 SWT Context、地点解析、州级资料与可复用的岗位预算输入。 |
| v0.5 | Decision Output & Budget Model | 增加岗位六维对比、含税回本与结余模型、缺项估值和逐步展开细节。 |
| v0.6 | SWT Market / Location Data Layer | 增加 BridgeUSA 州／城市 participant count、Community Support Groups、来源与匹配口径，并连接到现有地点和岗位流程。 |
| v0.7 | SWT English Assessment | 在 `swt-english` 中增加 ASSESS，以七维能力与不同场景权重支持 Agency、Sponsor、Host、Visa 和 Comprehensive 测评。 |
| v0.8 | SWT English Practice | 在 Assessment 基础上增加 PRACTICE、弱项训练、短反馈、Retry、Before／After 记录和 Reassessment 闭环。 |

v0.1 和 v0.2 根据早期开发历史还原，原始 Codex 日志不完整（Reconstructed from development history; original Codex logs incomplete）。完整历史见 [CHANGELOG.md](CHANGELOG.md)。
