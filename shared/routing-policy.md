# Intent Router

路由同时使用 `Task Type + SWT Stage + Known Context + Risk Level`，不得由单个关键词或阶段编号机械决定。

## 路由顺序

`Emergency check → Direct task / Homepage → Known Context → Intent → Stage → Risk → Specialist Skill`

1. 先判断紧急或红色风险并阻止不安全动作。
2. 没有实际任务的问候、help 或“怎么用”才显示首页；任务明确时直接处理。
3. 从当前 conversation、宿主上下文和已加载材料恢复已知事实，不重复询问。
4. Intent 表示用户此刻想完成什么；Stage 只限制可执行范围；Risk 决定能否给具体操作。
5. 只加载完成任务所需的最少 Skill；多 Intent 可连续调用多个 Skill，由 `swt` 合并。

## Task Type

| Intent | 识别目标 | 默认责任 |
|---|---|---|
| `NAVIGATION` | 我在哪一步、下一步做什么、现在准备什么 | `swt` |
| `DOCUMENT_CHECK` | 某份材料是否完整、正确或可继续使用 | 按文件对象路由 |
| `DECISION` | 在机构、Sponsor、城市、岗位或 Offer 间选择 | 机构／申请链到 application；岗位到 position |
| `INTERVIEW` | 准备或模拟 Sponsor／雇主面试 | `swt-english` |
| `ENGLISH_PRACTICE` | 口语、工作场景英语、表达纠错 | `swt-english` |
| `FORM_FILLING` | 表格或系统字段怎么填 | 申请系统到 application；签证表到 visa；抵美系统到 arrival |
| `CONFLICT` | 文件、通知、版本、日期或状态不一致 | `swt` 先判风险，再按对象路由 |
| `CALCULATION` | 预算、收入、启动现金或收益情景 | `swt-position` |
| `EMERGENCY` | 人身、医疗、犯罪、即时安全或重大身份紧急问题 | `swt` 先紧急分流，必要时 arrival |
| `GENERAL_QA` | 不属于以上类型的一般 SWT 问题 | `swt`；需专项知识时再路由 |

## 对象与责任

- 简历、视频、Application、Sponsor 系统、雇主申请、Offer 前材料，以及机构／Sponsor 报名、合同与付款：`swt-application`。
- Job Offer 的申请／签署状态到 `swt-application`；岗位、城市、工资、住宿、通勤、二工可行性和收益比较到 `swt-position`。
- Sponsor／雇主面试、口语和工作沟通演练：`swt-english`。
- DS-2019、DS-160、I-901 SEVIS Fee、签证预约、面签材料和跨文件冲突：`swt-visa`。
- 行前、机票、入境、I-94、SEVIS Check-in、SSN、保险、抵美后的 Sponsor 要求、换岗二工和项目结束：`swt-arrival`。

SEVIS Fee 与 SEVIS Check-in 是不同任务：前者属于签证链，后者属于抵美报到链。

## 语义示例

- “已经拿到 Offer，下一步是什么”是 `NAVIGATION`，由 `swt` 定位阶段；不能仅因出现 Offer 就调用 position。
- “这两个 Offer 哪个更适合我”是 `DECISION`，调用 `swt-position`。
- “这个岗位怎么准备英文面试”是 `INTERVIEW`，调用 `swt-english`；若岗位事实尚未核验，可先调用 position。
- “这个岗位值不值得去，再告诉我面试怎么准备”是 `DECISION + INTERVIEW`，依次调用 position 和 english，整合成一次回复。
- “时薪 16 刀、每周 40 小时、从 6 月 1 日到 9 月 1 日能剩多少”“把房租和税扣掉”“对比两个 Offer 最后剩得多”都是 `CALCULATION`，路由 `swt-position`。日期、周数、税务和汇率缺口按 Choice-first 逐项补足。

## 多 Skill 顺序

先处理紧急和红色风险，再处理阻塞其他任务的前置事实，然后依赖顺序调用必要 Specialist。最终只展示共同结论、必要专项结果和一条合并后的行动清单；事实、风险、问题和作者署名都不得重复。
