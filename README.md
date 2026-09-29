# SWT Plugin v0.5

面向美国 Summer Work Travel 参与者的全流程导航与六个专项 Skill：流程导航、申请、岗位、英语、签证和抵美事务。

## 安装与更新

唯一插件源码位于 `swt-skill/`。Codex 本地 marketplace 索引作为外部安装配置保留在 `../.agents/plugins/marketplace.json`，并直接指向本目录。安装或更新后运行：

```bash
codex plugin add swt-plugin@personal
```

安装或更新后开启新 conversation，让 Codex 重新发现 Skills。

## Source、Generated 与 Tests

| 目录／文件 | 职责 | 是否人工维护 |
|---|---|---|
| `skills/*/SKILL.md` | 六个 Skill 的入口与专项任务流程 | 是 |
| `shared/` | 跨 Skill 规则唯一真源 | 是 |
| `references/` | 跨模块知识、州级资料和默认值 | 是；`shared-runtime/` 除外 |
| `references/default-assumptions.json` | 岗位估算数字与税务规划参数的唯一真源 | 是；Skill 不复制具体数值 |
| `references/shared-runtime/*.md` | 从 `shared/` 生成的六份运行文件 | 否，运行 `sync_shared.py` |
| `scripts/` | 计算、路径、同步、校验、清理和重建工具 | 是 |
| `assets/` | 面向 Skill 的示例输入和可复用素材 | 是 |
| `tests/unit/` | 固定输入下的精确逻辑验证；用独立测试默认值 | 是 |
| `tests/integration/` | manifests、shared runtime、Skill discovery 与打包测试 | 是 |
| `tests/evals/cases/` | 用户行为场景与评审规则 | 是 |
| `tests/evals/fixtures/`、`expected/` | 匿名测试输入和预期结构 | 是 |

Skill 回答中的共享规则只在 `shared/` 编辑，再生成到 `references/shared-runtime/`。岗位估算参数只在 `references/default-assumptions.json` 修改；单测使用 `tests/unit/fixtures/position_assumptions.json`，生产默认值变化不会改写单测预期。

## 常用维护命令

```bash
python3 scripts/clean.py --cache
python3 scripts/clean.py --generated
python3 scripts/clean.py --tests
python3 scripts/clean.py --all
python3 scripts/sync_shared.py
python3 scripts/validate.py
python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/integration -v
python3 tests/test_plugin.py
python3 scripts/rebuild.py
```

`clean.py --all` 只清理源码包内已标记的生成运行文件、缓存和测试临时目录，不删除 `shared/`、`references/`、`SKILL.md`、业务素材或 eval fixtures。Codex 安装缓存只在提供某一个明确的 `--codex-plugin-cache` 路径后修剪旧版本；脚本会保留与当前源码版本一致的安装目录。

## 扁平 Skill 部署

WorkBuddy 等需要扁平目录结构时，从插件根目录执行：

```bash
python3 scripts/sync_shared.py --runtime-root /path/to/skills
```

该命令只写入目标部署目录，不改动 canonical source。
