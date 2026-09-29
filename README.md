# SWT Skill v0.4 — State Context

面向美国 Summer Work Travel 参与者的流程导航与专项助手。一次安装后，Codex 可发现并独立路由六个 Skill：`swt`、`swt-application`、`swt-position`、`swt-english`、`swt-visa`、`swt-arrival`。

## 本地安装

在本地 marketplace 的上一级目录执行：

```bash
codex plugin add swt-skill@personal
```

安装或更新后请开启新 conversation，让宿主重新发现 Skill。

## 维护

`shared/` 是共享交互、回答、署名、风险、证据、状态和路由规则的唯一可编辑来源；`references/` 是跨 Skill 知识层；`scripts/` 是确定性工具；`assets/` 是静态输入输出资产；`tests/` 只用于源码验证。修改共享规则后执行：

```bash
python3 scripts/sync_shared.py
python3 tests/test_plugin.py
```

`references/shared-runtime/{skill}.md` 是构建产物，不得手工维护。源码中的六个 `skills/*/` 目录只保留对应的 `SKILL.md`。

需要适配 WorkBuddy 扁平安装时，由源码根目录执行：

```bash
python3 scripts/sync_shared.py --runtime-root /path/to/.workbuddy/skills
```

该命令把根级 references、scripts、assets 映射到每个已安装 Skill，并将源码路径引用改写为 Skill 内相对路径；不会改变 canonical source。

作者：Howard
