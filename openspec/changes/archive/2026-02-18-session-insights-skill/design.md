## Context

`session-insights` 是一个 Claude Code 会话分析工具，当前以个人 slash command 形式存在于 `~/.claude/commands/`。它由两部分组成：

1. **Agent 指令**（`session-insights.md`，358 行）：定义交互引导、报告结构、Mermaid 图表规范
2. **数据提取脚本**（`session-insights.py`，444 行）：从 `~/.claude/projects/` 读取 JSONL 会话数据，输出结构化 JSON

目标仓库 xkcoding-skills 已有一个 Skill（desktop-kit），遵循 `SKILL.md` + `scripts/` + `references/` 的目录约定。参考了 baoyu-skills 生态中的最佳实践（`${SKILL_DIR}` 脚本引用模式、精简 frontmatter）。

## Goals / Non-Goals

**Goals:**
- 将 session-insights 转换为标准 Skill 格式，可通过仓库分享安装
- 采用 baoyu-skills 的 `${SKILL_DIR}` 模式解决脚本路径引用问题
- 输出路径加时间戳，支持历史快照保留
- 在 marketplace.json 注册并更新仓库 README

**Non-Goals:**
- 不改动 Python 脚本的核心逻辑（数据提取、解析算法）
- 不新增 Agent 分析能力或报告章节
- 不实现 Extension Support（`.baoyu-skills/` 覆盖机制）——初期不需要
- 不支持 Windows 路径兼容（当前脚本已是跨平台的）

## Decisions

### D1: 脚本引用采用 `${SKILL_DIR}` 占位符模式

**选择**：在 SKILL.md 中使用 `${SKILL_DIR}/scripts/session-insights.py`，并在文件开头包含标准 "Script Directory" 段落，指导 Agent 推断 SKILL_DIR。

**备选方案**：
- A) 硬编码 `~/.claude/skills/session-insights/scripts/...` — 不适用项目级安装
- B) 用 `find` 动态搜索脚本 — 不可靠，多安装位置可能冲突
- C) `${SKILL_DIR}` 占位符 — baoyu-skills 全系列验证过的模式 ✓

**理由**：Agent 加载 SKILL.md 时已知文件路径，推断目录是可靠的。这是 baoyu-skills 生态的事实标准。

### D2: Frontmatter 精简为 name + description

**选择**：只保留 `name` 和 `description` 两个字段。

**理由**：这是 Claude Code Skills 系统的标准格式，与 baoyu-skills 和 desktop-kit 一致。原 commands 格式中的 `category`、`complexity`、`mcp-servers`、`personas` 在 Skills 系统中无对应语义。

### D3: 输出路径加时间戳

**选择**：`./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`

**备选方案**：
- A) 覆盖式 `./docs/session-insights-{project-name}.md` — 丢失历史
- B) 递增序号 `...-001.md` — 需要扫描已有文件，复杂度高
- C) 时间戳后缀 — 简单、唯一、可排序 ✓

### D4: 不设 references/ 目录

**选择**：所有 Agent 指令集中在 SKILL.md 中，不拆分到 references/。

**理由**：session-insights 的指令虽然有 358 行，但是一个线性工作流（引导 → 脚本 → 分析 → 报告），没有 Agent 按需加载不同知识文档的场景。拆分反而增加 Agent 的读取步骤。

### D5: description 使用英文

**选择**：SKILL.md frontmatter 的 description 使用英文。

**理由**：Claude Code 的 skill 列表展示和自动补全中，英文 description 兼容性更好，且与 baoyu-skills、desktop-kit 保持一致。SKILL.md 正文和 README.md 仍使用中文。

## Risks / Trade-offs

- **[脚本执行环境]** 用户系统可能没有 Python 3 → SKILL.md 中加入前置检查提示，脚本失败时 Agent 应 fallback 到直接读取 JSONL
- **[JSONL 格式变更]** Claude Code 版本升级可能改变会话数据格式 → 脚本已有容错解析（`parse_message_field` 支持多种格式），风险可控
- **[大仓库性能]** 全量会话分析可能耗时较长 → 保留 `--last N` 参数，默认推荐 5 个会话
