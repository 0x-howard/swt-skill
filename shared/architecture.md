# SWT Skill v0.4 架构与责任归属

```text
swt-skill/
├── skills/*/SKILL.md               六个可独立发现的 Skill 行为规则
├── references/                     跨 Specialist 共用知识层与运行时资料
│   ├── knowledge/state_context/    唯一州级 State Context
│   └── shared-runtime/             由 shared/ 同步生成
├── shared/                         共享规则唯一可编辑真源
├── scripts/                        确定性工具与部署映射
├── assets/                         数据与输入模板
└── tests/                          结构、脚本与行为验收
```

用户安装一次 Plugin。宿主发现 `skills/` 下六个 Skill，并按各自 frontmatter 独立路由。

## 共享规则策略

根目录 `shared/` 是唯一可编辑真源。`scripts/sync_shared.py` 将每个 Skill 所需的共享规则生成到根 `references/shared-runtime/{skill}.md`；生成文件不得手工编辑，修改共享规则后必须重新同步，并用 `--check` 验证无漂移。使用 `--runtime-root` 时，脚本才将这些根级资料映射到 WorkBuddy 的扁平 Skill 目录。

源码与部署布局分离：源码的 `skills/` 只保留六个 `SKILL.md`；扁平部署由同步脚本把 `references/`、`scripts/`、`assets/` 和对应运行时规则映射到每个 `~/.workbuddy/skills/{skill}/` 下。

## 责任边界

- `swt`：首页、导航、状态恢复、Intent／Stage／Risk 路由、多 Skill 协调。
- `swt-application`：报名与申请链、材料、系统、机构／Sponsor 合同付款和 Offer 流程完整性。
- `swt-position`：岗位／城市／住房／通勤比较、二工可行性和预算情景。
- `swt-english`：Sponsor／雇主面试、工作沟通、口语模拟与纠错。
- `swt-visa`：DS-2019、DS-160、SEVIS Fee、预约、面签、签证材料和冲突。
- `swt-arrival`：行前、入境、SEVIS Check-in、I-94、SSN、保险、变更与项目结束。

脚本只处理确定性计算、校验和构建，不代替业务判断。长期跨 conversation 状态若将来需要，应单独实现 Persistence Layer，不能塞进 Specialist Skill。

## 州级 SWT Knowledge Layer

`references/knowledge/state_context/` 是共享知识层，不属于 `swt-position` 私有数据。`STATE_INDEX.md` 只负责“地点 → 州”的精确路由；`states/{STATE}.md` 使用统一的产品字段保存州级 SWT 背景。`swt-position` 用它比较 Offer，`swt-arrival` 后续可复用同一资料处理落地便利问题。

州级资料不得伪装为城市数据库，也不得覆盖 Offer 的明确条件。它不进入现有预算脚本的自动税务计算。

维护 State MD 时，数据优先级为：当前官方资料（最低工资、州所得税、销售税等规则）→ 当前市场资料 → `Raw_ZH` 的匿名经验 → 经审慎交叉核对的社区经验。`Raw_ZH` 按 C9 分州，C12–C23 仅用于已有 Schema 能承载的工资、工时、住宿、基础开销、交通、二工和落地便利判断；C14、C19 等未在产品 Schema 中单列的字段只作交叉核验，不额外增加展示字段。问卷经验只能写成州级参考，不能输出样本量、成功率或城市级结论。
