# xkcoding-skills — Claude Code Skills 仓库

## 项目概览

个人 Claude Code Skills marketplace 仓库。每个 Skill 是一个目录，包含 SKILL.md（Agent 指令）+ references/（知识文档）+ scripts/（工具脚本）。

## 当前 Skills

### desktop-kit（MVP）

将任意 Web App（React/Vue/静态页面）打包为 macOS 桌面客户端。

**核心设计文档**：`desktop-kit/DESIGN.md` — 包含完整的设计思路、知识来源、架构决策和实现规划。该文档沉淀了从 Argus 项目中提炼的全部工程经验，**实现前务必先读此文档**。

### session-insights（Stable）

分析 Claude Code 会话数据，生成带 Mermaid 图表的 Markdown 洞察报告。支持四种模式：概览、逐个详细、并行详细（`claude -p` 真并行）、后台详细。

**结构**：
- `session-insights/SKILL.md` — Agent 指令入口，含 AskUserQuestion 路由和分流逻辑
- `session-insights/scripts/session-insights.py` — 数据提取（纯 Python 标准库）
- `session-insights/scripts/session-insights-analyze.py` — 并行分析编排（ThreadPoolExecutor + `claude -p`）
- `session-insights/references/parallel-prompt.md` — 并行模式执行指令

## 开发规范

- Skill 入口文件必须是 `SKILL.md`，含 YAML frontmatter（name + description）
- 知识文档放 `references/`，可执行脚本放 `scripts/`
- marketplace 注册在 `.claude-plugin/marketplace.json`
- 中文注释和文档，代码标识符保持英文

## OpenSpec 使用

本仓库使用 OpenSpec 管理变更。实现 desktop-kit 时：

1. 先读 `desktop-kit/DESIGN.md` 了解完整上下文
2. 用 `/opsx:new desktop-kit-mvp` 创建变更
3. 按 DESIGN.md 第 10 节的优先级逐步实现
